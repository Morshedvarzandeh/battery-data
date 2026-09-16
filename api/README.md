# Operating the Lemonergy paid API

The hosted entrypoint is `api.hosted.app:create_app` (FastAPI/Uvicorn).
`api/server.py` remains the legacy, unauthenticated local read API. It is not the
hosted service and is never started by `api/Dockerfile`.

## Separation of public data and private service state

- Accepted `contrib/` records produce an immutable JSON read snapshot, just as
  the web catalog is derived from accepted contributions. The relational core
  and its validated contribution workflow retain their existing role.
- `review/`, patent candidates and demonstration SQL seeds never enter it.
- Every value, condition, bound, source and locator is retained. Search summaries
  link to full records and the exact Git commit.
- PostgreSQL schema `lemonergy_api` stores private customer labels, hashed keys,
  payment references, usage counters and an operator audit. Use a **separate
  service database**. Do not publish its contents or include it in free exports.
- No HTTP administration or unauthenticated data route exists in the hosted app.

## 1. Install and create private service tables

Use Python 3.11+ and PostgreSQL 16+. In a virtual environment:

```bash
pip install -r api/requirements.txt
```

Provision an empty database named, for example, `lemonergy_service`. Set
`LEMONERGY_ADMIN_DATABASE_URL` in your private operator environment to its owner
connection string. Use TLS for remote database connections. No default database
password or trial account is provided.

```bash
python -m api.hosted.admin migrate
```

This creates only the private schema and is safe to rerun. **Do not run
`setup.sh` or `tools/build_db.sh` against this database**: those scripts rebuild
the research database and are unrelated to paid-service deployment.

Create a separate PostgreSQL LOGIN role for the API process using your database
provider or `psql`. Give it a strong private password, no superuser, no database
creation and no role creation permissions. Grant it access using:

```bash
python -m api.hosted.admin grant-runtime --role lemonergy_api
```

Set `LEMONERGY_DATABASE_URL` in the API runtime to this restricted role's DSN.
Keep the owner DSN in the operator environment only. The runtime can check keys
and update counters; it cannot grant payment access, change plans, create keys,
reverse revocations or read the audit table. It has limited key-label UPDATE
permission because PostgreSQL row locking requires some UPDATE privilege.

## 2. Activate a customer after payment

The initial release supports an operator-managed paid pilot. Agree a price,
monthly request allowance, request rate and access period with the customer;
collect payment using your existing process. These commands **record confirmed
payment**; they do not charge a card or verify an invoice with a payment provider.
Automatic checkout/subscription webhooks are not implemented.

```bash
# Example allowances, not a published commercial plan:
python -m api.hosted.admin create-account \
  --label 'Pilot customer' --monthly-limit 10000 --minute-limit 60
```

The response includes an account UUID; set it as `CUSTOMER_ID` in the operator
shell. Set `PAID_UNTIL` to the agreed end of access as an ISO 8601 timestamp with
timezone (for example a future date ending in `T00:00:00Z`). Set
`PAYMENT_REFERENCE` to your internal reference for the confirmed payment.

```bash
python -m api.hosted.admin activate --account "$CUSTOMER_ID" \
  --paid-until "$PAID_UNTIL" --payment-reference "$PAYMENT_REFERENCE"
mkdir -p api/private
python -m api.hosted.admin issue-key --account "$CUSTOMER_ID" \
  --label 'Production integration' --expires-at "$PAID_UNTIL" \
  --output api/private/customer.key
```

The secret is written once to a new file with mode `0600`; it is never printed
by the CLI. Store/deliver it using your existing secure channel. PostgreSQL holds
only its SHA-256 digest. Keys contain 256 bits of random entropy. The returned
key UUID is safe to use for administration. Record it as `KEY_ID`.

```bash
python -m api.hosted.admin inspect --account "$CUSTOMER_ID"
python -m api.hosted.admin revoke-key --key-id "$KEY_ID"
python -m api.hosted.admin suspend --account "$CUSTOMER_ID"
python -m api.hosted.admin set-limits --account "$CUSTOMER_ID" \
  --monthly-limit 20000 --minute-limit 120
```

Renew by recording the next confirmed payment with `activate`. This does not
reset usage or extend a key's expiry. Issue a replacement key when necessary and
revoke the old key after rotation. Refunds or withdrawn access require a manual
`suspend`; no external billing system is connected. Audit entries preserve the
payment reference, access expiry and key administration events without secrets.

## 3. Build a release and run

Build from a clean, reviewed checkout so source links correspond to the data.

```bash
python -m api.hosted.catalog --revision "$(git rev-parse HEAD)" --output api/catalog.json
uvicorn api.hosted.app:create_app --factory --host 127.0.0.1 --port 8000 \
  --workers 2 --no-access-log --no-proxy-headers
```

For a container, build from the repository root:

```bash
docker build -f api/Dockerfile --build-arg SOURCE_REVISION="$(git rev-parse HEAD)" \
  -t lemonergy-battery-api .
docker run --rm --read-only --tmpfs /tmp --cap-drop ALL \
  --security-opt no-new-privileges -p 127.0.0.1:8000:8000 \
  --env LEMONERGY_DATABASE_URL lemonergy-battery-api
```

The image runs as a non-root user and starts only the authenticated service.
Do not pass `LEMONERGY_ADMIN_DATABASE_URL` to it. `api/.env.example` documents
runtime configuration; real `.env`, `.key` and `private/` files are ignored by
Git and excluded from the Docker context.

Put a TLS reverse proxy or managed HTTPS service in front of port 8000. Keep
8000 and the database off the public network. Configure edge connection/request
limits (including unauthenticated requests), timeouts, maximum header size and
log redaction for `X-API-Key`. Do not log query strings or headers. Uvicorn access
logging is disabled so an accidentally supplied URL credential isn't recorded.
The service is server-to-server and does not enable cross-origin browser access.

Monitor `/healthz`, errors and database availability, and back up the private
service database. No startup migration grants paid access. Missing configuration,
unavailable PostgreSQL or an invalid snapshot cannot fall back to a free API.

Deploy the same snapshot to every worker/replica. Use an atomic release switch
or drain old replicas so paginated clients see one catalog hash. Clients get
`409` if they cross releases. Source data is frozen until the next deployment.

## Accounting and validation

Account row locks serialize requests across workers and customer keys. The
payment/key checks, monthly accounting and minute accounting run in the same
transaction; failed record lookup, encoding or query work rolls back the charge.
Database time determines payment expiry and quota periods. A client disconnect
after commit cannot undo the charge. Minute limits use fixed UTC buckets; allow
for a burst across the minute boundary at your edge proxy.

```bash
pip install -r api/requirements-test.txt
python -m unittest discover -s tests -p 'test_hosted_catalog.py'
# Against a disposable database; test role creation needs a DB administrator:
LEMONERGY_TEST_DATABASE_URL='YOUR_PRIVATE_TEST_DSN' python tests/ci_hosted_api.py
```

CI exercises actual PostgreSQL privileges, revocation, expiry, multiple keys,
concurrent worker quotas, rollback, pagination, evidence preservation and the
review boundary. No live payment or hosting service is configured by these tests.

Implementation references: [FastAPI API keys](https://fastapi.tiangolo.com/reference/security/),
[PostgreSQL row locking](https://www.postgresql.org/docs/current/explicit-locking.html),
[Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).
