"""Durable paid entitlements and atomic per-customer usage accounting."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Callable

import psycopg
from psycopg.rows import dict_row


class AccessError(Exception):
    def __init__(self, status, code, message, headers=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.headers = headers or {}


def key_digest(key):
    return hashlib.sha256(key.encode()).hexdigest()


class AccessStore:
    def __init__(self, dsn):
        if not dsn:
            raise ValueError("LEMONERGY_DATABASE_URL is required; anonymous mode is not supported")
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(self.dsn, connect_timeout=3, row_factory=dict_row,
                               options="-c statement_timeout=5000 -c lock_timeout=3000")

    def health(self):
        with self.connect() as conn:
            conn.execute("SELECT 1 FROM lemonergy_api.account LIMIT 1")
            conn.execute("SELECT 1 FROM lemonergy_api.api_key LIMIT 1")
            conn.execute("SELECT 1 FROM lemonergy_api.monthly_usage LIMIT 1")

    def run(self, raw_key: str | None, operation: Callable, charge=True):
        if not raw_key or not re.fullmatch(r"lem_live_[A-Za-z0-9_-]{43}", raw_key):
            raise AccessError(401, "invalid_api_key", "A valid X-API-Key header is required.",
                              {"WWW-Authenticate": 'APIKey realm="Lemonergy"'})
        # All workers and all keys for an account serialize on the same account
        # row. Both quota reservation and result construction commit together.
        with self.connect() as conn:
            account = conn.execute("""
                SELECT a.*, k.expires_at, k.revoked_at
                  FROM lemonergy_api.api_key k
                  JOIN lemonergy_api.account a ON a.id = k.account_id
                 WHERE k.digest = %s FOR UPDATE OF a, k
            """, (key_digest(raw_key),)).fetchone()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"].astimezone(timezone.utc)
            if not account or account["revoked_at"] or account["expires_at"] <= now:
                raise AccessError(401, "invalid_api_key", "The API key is invalid, expired or revoked.",
                                  {"WWW-Authenticate": 'APIKey realm="Lemonergy"'})
            if not account["enabled"]:
                raise AccessError(403, "account_inactive", "This customer account is inactive.")
            if not account["paid_until"] or account["paid_until"] <= now:
                raise AccessError(402, "payment_required", "Paid access has expired or has not been activated.")
            month = now.date().replace(day=1)
            next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
            month_reset = datetime.combine(next_month, datetime.min.time(), tzinfo=timezone.utc)
            minute = now.replace(second=0, microsecond=0)
            minute_reset = minute + timedelta(minutes=1)
            minute_used = account["minute_used"] if account["minute_start"] == minute else 0
            conn.execute("""INSERT INTO lemonergy_api.monthly_usage(account_id, month)
                            VALUES (%s, %s) ON CONFLICT DO NOTHING""", (account["id"], month))
            used = conn.execute("""SELECT used FROM lemonergy_api.monthly_usage
                                    WHERE account_id = %s AND month = %s""", (account["id"], month)).fetchone()["used"]
            if minute_used >= account["minute_limit"]:
                raise AccessError(429, "rate_limit_exceeded", "Per-minute request limit reached.",
                                  {"Retry-After": str(max(1, int((minute_reset - now).total_seconds()) + 1))})
            if charge and used >= account["monthly_limit"]:
                raise AccessError(429, "monthly_quota_exceeded", "Monthly request allowance reached.",
                                  {"Retry-After": str(max(1, int((month_reset - now).total_seconds()) + 1))})
            usage = {"account_id": str(account["id"]), "month": month.isoformat(),
                     "requests_used": used + int(charge), "monthly_limit": account["monthly_limit"],
                     "requests_remaining": max(0, account["monthly_limit"] - used - int(charge)),
                     "resets_at": month_reset.isoformat(), "requests_per_minute": account["minute_limit"],
                     "paid_until": account["paid_until"].isoformat()}
            result = operation(usage)  # Any exception rolls back both counters.
            conn.execute("""UPDATE lemonergy_api.account SET minute_start = %s, minute_used = %s
                            WHERE id = %s""", (minute, minute_used + 1, account["id"]))
            if charge:
                conn.execute("""UPDATE lemonergy_api.monthly_usage SET used = used + 1
                                WHERE account_id = %s AND month = %s""", (account["id"], month))
        return result, {"X-RateLimit-Limit": str(account["minute_limit"]),
                        "X-RateLimit-Remaining": str(account["minute_limit"] - minute_used - 1),
                        "X-RateLimit-Reset": str(int(minute_reset.timestamp())),
                        "X-Monthly-Limit": str(account["monthly_limit"]),
                        "X-Monthly-Remaining": str(usage["requests_remaining"])}
