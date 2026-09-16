"""Real PostgreSQL + ASGI tests. Run against a disposable, empty service database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from api.hosted.access import AccessStore, AccessError, key_digest
from api.hosted.admin import MIGRATION, activate, create_account, grant_runtime, issue_key, revoke_key
from api.hosted.app import create_app, ProductQuery
from api.hosted.catalog import Catalog, build

DSN = os.environ["LEMONERGY_TEST_DATABASE_URL"]


class HostedApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = AccessStore(DSN)
        cls.role = "api_test_" + uuid.uuid4().hex
        cls.password = uuid.uuid4().hex
        with cls.admin.connect() as conn:
            conn.execute(MIGRATION.read_text())
            conn.execute(MIGRATION.read_text())  # Safe migration rerun.
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(cls.role), sql.Literal(cls.password)))
            grant_runtime(conn, cls.role)
        cls.runtime_dsn = make_conninfo(DSN, user=cls.role, password=cls.password)
        cls.catalog = Catalog(build(ROOT, "1" * 40))

    @classmethod
    def tearDownClass(cls):
        with cls.admin.connect() as conn:
            conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(cls.role)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(cls.role)))

    def setUp(self):
        self.store = AccessStore(self.runtime_dsn)
        self.paid_until = datetime.now(timezone.utc) + timedelta(days=45)
        with self.admin.connect() as conn:
            self.account = create_account(conn, "CI customer", 100, 200)
            activate(conn, self.account, self.paid_until, "CI paid invoice")
            self.key_id, self.key = issue_key(conn, self.account, "CI key", self.paid_until)
        self.client = TestClient(create_app(self.catalog, self.store), raise_server_exceptions=False)
        self.headers = {"X-API-Key": self.key}

    def used(self):
        with self.admin.connect() as conn:
            return conn.execute("SELECT COALESCE(sum(used), 0) AS n FROM lemonergy_api.monthly_usage WHERE account_id = %s", (self.account,)).fetchone()["n"]

    def get(self, path):
        return self.client.get(path, headers=self.headers)

    def test_all_data_routes_require_header_and_no_local_api_bypass(self):
        for path in ["/v1/products", "/v1/batteries", "/v1/components", "/v1/manufacturers", "/v1/usage", "/v1/products/cell/samsung-sdi/inr21700-50e"]:
            self.assertEqual(401, self.client.get(path).status_code, path)
        for path in ["/v1/cells", "/v1/packs", "/contrib/cells/samsung-sdi/inr21700-50e.yaml", "/catalog.json"]:
            self.assertEqual(404, self.client.get(path).status_code)
        self.assertEqual(422, self.client.get("/v1/products", params={"api_key": self.key}).status_code)
        self.assertEqual(0, self.used())

    def test_public_docs_health_and_openapi_security(self):
        for path in ["/", "/docs", "/healthz", "/openapi.json"]:
            self.assertEqual(200, self.client.get(path).status_code)
        spec = self.client.get("/openapi.json").json()
        for path, methods in spec["paths"].items():
            if path.startswith("/v1/"):
                self.assertTrue(methods["get"]["security"], path)
        self.assertEqual(0, self.used())

    def test_paid_queries_full_provenance_and_pagination(self):
        r = self.get("/v1/products?limit=1")
        self.assertEqual(200, r.status_code, r.text)
        self.assertEqual(len(self.catalog.entries), r.json()["meta"]["total"])
        self.assertEqual("99", r.headers["X-Monthly-Remaining"])
        second = self.get(r.json()["links"]["next"])
        self.assertNotEqual(r.json()["data"][0], second.json()["data"][0])
        detail = self.get("/v1/products/cell/samsung-sdi/inr21700-50e").json()["data"]
        self.assertEqual(self.catalog.detail("cell/samsung-sdi/inr21700-50e"), detail)
        self.assertEqual("no-store", r.headers["Cache-Control"])
        self.assertEqual(3, self.used())

    def test_review_candidates_never_exposed(self):
        r = self.get("/v1/components")
        expected = self.catalog.counts.get("component", 0)
        self.assertEqual(expected, r.json()["meta"]["total"])
        self.assertEqual(404, self.get("/v1/products/component/sensata-gigavac/gv211bax").status_code)
        batteries = self.get("/v1/batteries?kind=primary_cell").json()
        self.assertGreater(batteries["meta"]["total"], 0)
        self.assertTrue(all(x["product"]["kind"] == "primary_cell" for x in batteries["data"]))

    def test_filter_matches_same_observation_and_native_unit(self):
        for params, expected in [
            ("quantity=capacity&unit=mAh&statistic=rated&min_value=4800", 0),
            ("quantity=capacity&unit=mAh&statistic=standard&min_value=4800", 1),
            ("quantity=capacity&unit=Ah&min_value=4", 0),
        ]:
            r = self.get("/v1/batteries?q=inr21700-50e&" + params)
            self.assertEqual(expected, r.json()["meta"]["total"], r.text)
        self.assertEqual(0, self.get("/v1/products?manufacturer=%27%20OR%201%3D1--").json()["meta"]["total"])

    def test_invalid_bounds_and_failed_requests_dont_charge(self):
        for query in ["limit=-1", "limit=101", "offset=-1", "limit=wat", "quantity=capacity", "min_value=NaN", "kind=unknown", "unit=Ah", "quantity=capacity&unit=Ah&min_value=5&max_value=2", "unknown=1"]:
            r = self.get("/v1/products?" + query)
            self.assertEqual(422, r.status_code, r.text)
        self.assertEqual(404, self.get("/v1/products/does/not/exist").status_code)
        self.assertEqual(409, self.get("/v1/products?release=" + "0" * 64).status_code)
        self.assertEqual(0, self.used())

    def test_invalid_expired_and_revoked_keys(self):
        r = self.client.get("/v1/products", headers={"X-API-Key": "lem_live_" + "x" * 43})
        self.assertEqual(401, r.status_code)
        with self.admin.connect() as conn:
            revoke_key(conn, self.key_id)
        self.assertEqual(401, self.get("/v1/products").status_code)
        with self.admin.connect() as conn:
            conn.execute("UPDATE lemonergy_api.api_key SET revoked_at=NULL, expires_at=now()-interval '1 second' WHERE id=%s", (self.key_id,))
        self.assertEqual(401, self.get("/v1/products").status_code)
        self.assertEqual(0, self.used())

    def test_payment_expiry_and_suspension(self):
        with self.admin.connect() as conn:
            conn.execute("UPDATE lemonergy_api.account SET paid_until=now()-interval '1 second' WHERE id=%s", (self.account,))
        self.assertEqual(402, self.get("/v1/products").status_code)
        with self.admin.connect() as conn:
            conn.execute("UPDATE lemonergy_api.account SET enabled=false WHERE id=%s", (self.account,))
        self.assertEqual(403, self.get("/v1/products").status_code)
        self.assertEqual(0, self.used())

    def test_monthly_quota_shared_between_keys_and_workers(self):
        with self.admin.connect() as conn:
            conn.execute("UPDATE lemonergy_api.account SET monthly_limit=5 WHERE id=%s", (self.account,))
            _, key2 = issue_key(conn, self.account, "second key", self.paid_until)
        def request(i):
            # Distinct app and DB connection simulate independent worker processes.
            client = TestClient(create_app(self.catalog, AccessStore(self.runtime_dsn)))
            return client.get("/v1/products?limit=1", headers={"X-API-Key": self.key if i % 2 else key2}).status_code
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(request, range(18)))
        self.assertEqual(5, results.count(200), results)
        self.assertEqual(13, results.count(429), results)
        self.assertEqual(5, self.used())
        usage = self.get("/v1/usage")
        self.assertEqual(200, usage.status_code)
        self.assertEqual(0, usage.json()["data"]["requests_remaining"])
        self.assertEqual(5, self.used())

    def test_minute_limit_and_reset(self):
        with self.admin.connect() as conn:
            conn.execute("UPDATE lemonergy_api.account SET minute_limit=1 WHERE id=%s", (self.account,))
        self.assertEqual(200, self.get("/v1/products").status_code)
        r = self.get("/v1/products")
        self.assertEqual(429, r.status_code)
        self.assertGreater(int(r.headers["Retry-After"]), 0)
        with self.admin.connect() as conn:
            conn.execute("UPDATE lemonergy_api.account SET minute_start=now()-interval '2 minutes' WHERE id=%s", (self.account,))
        self.assertEqual(200, self.get("/v1/products").status_code)

    def test_previous_month_and_other_customer_dont_affect_quota(self):
        with self.admin.connect() as conn:
            conn.execute("""INSERT INTO lemonergy_api.monthly_usage VALUES (%s, '2000-01-01', 100000)""", (self.account,))
        self.assertEqual(200, self.get("/v1/products").status_code)
        usage = self.get("/v1/usage").json()["data"]
        self.assertEqual(1, usage["requests_used"])
        self.assertEqual(str(self.account), usage["account_id"])
        self.assertNotIn("digest", str(usage))

    def test_transaction_rolls_back_on_result_failure(self):
        def broken(_): raise ValueError("private failure")
        with self.assertRaises(ValueError): self.store.run(self.key, broken)
        self.assertEqual(0, self.used())
        with self.admin.connect() as conn:
            self.assertEqual(0, conn.execute("SELECT minute_used FROM lemonergy_api.account WHERE id=%s", (self.account,)).fetchone()["minute_used"])

    def test_database_failure_is_closed_and_redacted(self):
        bad = AccessStore("host=127.0.0.1 port=1 dbname=secret_db user=secret_customer password=never_expose")
        client = TestClient(create_app(self.catalog, bad), raise_server_exceptions=False)
        r = client.get("/v1/products", headers=self.headers)
        self.assertEqual(503, r.status_code)
        self.assertNotIn("secret", r.text); self.assertNotIn("never_expose", r.text)

    def test_runtime_cannot_grant_access_or_read_audit(self):
        for statement in ["UPDATE lemonergy_api.account SET paid_until=now()+interval '1 year'", "UPDATE lemonergy_api.api_key SET revoked_at=NULL", "SELECT * FROM lemonergy_api.audit"]:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.store.connect() as conn: conn.execute(statement)
        with self.admin.connect() as conn:
            row = conn.execute("SELECT digest FROM lemonergy_api.api_key WHERE id=%s", (self.key_id,)).fetchone()
            self.assertEqual(key_digest(self.key), row["digest"])
            self.assertNotEqual(self.key, row["digest"])


if __name__ == "__main__": unittest.main(verbosity=2)
