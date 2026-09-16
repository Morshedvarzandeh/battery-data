"""Operator-only CLI. No administration endpoint is exposed on the public API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import uuid

from psycopg import sql
from psycopg.types.json import Jsonb

from .access import AccessStore, key_digest

MIGRATION = Path(__file__).resolve().parents[1] / "migrations/001_access.sql"


def audit(conn, account_id, action, detail):
    conn.execute("INSERT INTO lemonergy_api.audit(account_id, action, detail) VALUES (%s, %s, %s)",
                 (account_id, action, Jsonb(detail)))


def timestamp(text):
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise argparse.ArgumentTypeError("include a timezone, for example 2026-12-01T00:00:00Z")
    return value.astimezone(timezone.utc)


def positive(text):
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def create_account(conn, label, monthly_limit, minute_limit):
    account_id = uuid.uuid4()
    conn.execute("""INSERT INTO lemonergy_api.account(id, label, monthly_limit, minute_limit)
                    VALUES (%s, %s, %s, %s)""", (account_id, label, monthly_limit, minute_limit))
    audit(conn, account_id, "created", {"monthly_limit": monthly_limit, "minute_limit": minute_limit})
    return account_id


def activate(conn, account_id, paid_until, payment_reference):
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if paid_until <= now:
        raise ValueError("paid-until must be in the future")
    if not payment_reference.strip():
        raise ValueError("record a payment reference")
    row = conn.execute("""UPDATE lemonergy_api.account SET enabled = true, paid_until = %s
                          WHERE id = %s RETURNING id""", (paid_until, account_id)).fetchone()
    if not row:
        raise ValueError("unknown account")
    audit(conn, account_id, "payment_recorded", {"paid_until": paid_until.isoformat(), "reference": payment_reference})


def issue_key(conn, account_id, label, expires_at):
    account = conn.execute("SELECT * FROM lemonergy_api.account WHERE id = %s FOR UPDATE", (account_id,)).fetchone()
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if not account or not account["enabled"] or not account["paid_until"] or account["paid_until"] <= now:
        raise ValueError("activate paid access before issuing a key")
    if expires_at <= now:
        raise ValueError("key expiry must be in the future")
    key_id, key = uuid.uuid4(), "lem_live_" + secrets.token_urlsafe(32)
    conn.execute("""INSERT INTO lemonergy_api.api_key(id, account_id, digest, label, expires_at)
                    VALUES (%s, %s, %s, %s, %s)""", (key_id, account_id, key_digest(key), label, expires_at))
    audit(conn, account_id, "key_issued", {"key_id": str(key_id), "expires_at": expires_at.isoformat()})
    return key_id, key


def revoke_key(conn, key_id):
    row = conn.execute("""UPDATE lemonergy_api.api_key SET revoked_at = COALESCE(revoked_at, now())
                          WHERE id = %s RETURNING account_id""", (key_id,)).fetchone()
    if not row:
        raise ValueError("unknown key")
    audit(conn, row["account_id"], "key_revoked", {"key_id": str(key_id)})


def grant_runtime(conn, role):
    # The DBA creates the LOGIN role and its secret separately. No password in
    # command arguments, generated source files or repository configuration.
    target = sql.Identifier(role)
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA lemonergy_api TO {}").format(target))
    conn.execute(sql.SQL("GRANT SELECT ON lemonergy_api.account, lemonergy_api.api_key, lemonergy_api.monthly_usage TO {}").format(target))
    # FOR UPDATE needs UPDATE privilege on at least one column. These columns
    # cannot change a key's digest, expiry, revocation or account affiliation.
    conn.execute(sql.SQL("GRANT UPDATE (label) ON lemonergy_api.api_key TO {}").format(target))
    conn.execute(sql.SQL("GRANT UPDATE (minute_start, minute_used) ON lemonergy_api.account TO {}").format(target))
    conn.execute(sql.SQL("GRANT INSERT, UPDATE ON lemonergy_api.monthly_usage TO {}").format(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    p = commands.add_parser("grant-runtime"); p.add_argument("--role", required=True)
    p = commands.add_parser("create-account")
    p.add_argument("--label", required=True); p.add_argument("--monthly-limit", type=positive, required=True)
    p.add_argument("--minute-limit", type=positive, required=True)
    p = commands.add_parser("activate")
    p.add_argument("--account", type=uuid.UUID, required=True)
    p.add_argument("--paid-until", type=timestamp, required=True)
    p.add_argument("--payment-reference", required=True)
    p = commands.add_parser("issue-key")
    p.add_argument("--account", type=uuid.UUID, required=True); p.add_argument("--label", required=True)
    p.add_argument("--expires-at", type=timestamp, required=True)
    p.add_argument("--output", type=Path, required=True, help="New private file; never prints the secret to stdout")
    p = commands.add_parser("revoke-key"); p.add_argument("--key-id", type=uuid.UUID, required=True)
    p = commands.add_parser("suspend"); p.add_argument("--account", type=uuid.UUID, required=True)
    p = commands.add_parser("set-limits")
    p.add_argument("--account", type=uuid.UUID, required=True)
    p.add_argument("--monthly-limit", type=positive, required=True); p.add_argument("--minute-limit", type=positive, required=True)
    p = commands.add_parser("inspect"); p.add_argument("--account", type=uuid.UUID, required=True)
    args = parser.parse_args()
    created_output = False
    output = {}
    try:
        store = AccessStore(os.environ.get("LEMONERGY_ADMIN_DATABASE_URL"))
        with store.connect() as conn:
            if args.command == "migrate":
                conn.execute(MIGRATION.read_text())
                output = {"migration": "001_access", "status": "applied"}
            elif args.command == "grant-runtime":
                grant_runtime(conn, args.role); output = {"role": args.role, "status": "granted"}
            elif args.command == "create-account":
                output = {"account_id": str(create_account(conn, args.label, args.monthly_limit, args.minute_limit)), "enabled": False}
            elif args.command == "activate":
                activate(conn, args.account, args.paid_until, args.payment_reference)
                output = {"account_id": str(args.account), "paid_until": args.paid_until.isoformat()}
            elif args.command == "issue-key":
                # O_EXCL refuses overwrites/symlinks; mode 0600 keeps keys private.
                fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created_output = True
                with os.fdopen(fd, "w") as stream:
                    key_id, key = issue_key(conn, args.account, args.label, args.expires_at)
                    stream.write(key + "\n"); stream.flush(); os.fsync(stream.fileno())
                output = {"key_id": str(key_id), "secret_file": str(args.output), "expires_at": args.expires_at.isoformat()}
            elif args.command == "revoke-key":
                revoke_key(conn, args.key_id); output = {"key_id": str(args.key_id), "status": "revoked"}
            elif args.command in {"suspend", "set-limits"}:
                if args.command == "suspend":
                    row = conn.execute("UPDATE lemonergy_api.account SET enabled = false WHERE id = %s RETURNING id", (args.account,)).fetchone()
                    detail = {"enabled": False}
                else:
                    row = conn.execute("""UPDATE lemonergy_api.account SET monthly_limit = %s, minute_limit = %s
                                          WHERE id = %s RETURNING id""", (args.monthly_limit, args.minute_limit, args.account)).fetchone()
                    detail = {"monthly_limit": args.monthly_limit, "minute_limit": args.minute_limit}
                if not row: raise ValueError("unknown account")
                audit(conn, args.account, args.command, detail)
                output = {"account_id": str(args.account), **detail}
            elif args.command == "inspect":
                account = conn.execute("SELECT * FROM lemonergy_api.account WHERE id = %s", (args.account,)).fetchone()
                if not account: raise ValueError("unknown account")
                keys = conn.execute("""SELECT id, label, expires_at, revoked_at, created_at FROM lemonergy_api.api_key
                                       WHERE account_id = %s ORDER BY created_at""", (args.account,)).fetchall()
                usage = conn.execute("SELECT month, used FROM lemonergy_api.monthly_usage WHERE account_id = %s ORDER BY month", (args.account,)).fetchall()
                output = {"account": account, "keys": keys, "usage": usage}
        print(json.dumps(output, default=str))
    except Exception as exc:
        if created_output:
            args.output.unlink(missing_ok=True)
        # psycopg errors may contain DSNs or customer details. Do not print them.
        parser.exit(1, f"Operation failed: {str(exc) if isinstance(exc, ValueError) else type(exc).__name__}\n")


if __name__ == "__main__":
    main()
