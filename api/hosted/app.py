"""Run with: uvicorn api.hosted.app:create_app --factory --host 0.0.0.0."""
from __future__ import annotations

from collections import Counter
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, model_validator
import psycopg
from starlette.exceptions import HTTPException as StarletteHTTPException

from .access import AccessError, AccessStore
from .catalog import Catalog, REPOSITORY

KINDS = Literal["cell", "primary_cell", "module", "pack", "system", "component"]
COMPONENTS = Literal["contactor", "precharge_contactor", "fuse", "inverter", "dc_dc_converter", "charger"]
key_header = APIKeyHeader(name="X-API-Key", auto_error=False,
                          description="Paid customer key. Keep it on your server; never in a URL or browser bundle.")
ApiKey = Annotated[str | None, Security(key_header)]


class ProductQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    q: str | None = Field(default=None, min_length=1, max_length=150)
    manufacturer: str | None = Field(default=None, min_length=1, max_length=150)
    kind: KINDS | None = None
    component_type: COMPONENTS | None = None
    chemistry: str | None = Field(default=None, min_length=1, max_length=100)
    quantity: str | None = Field(default=None, min_length=1, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    statistic: str | None = Field(default=None, min_length=1, max_length=40)
    min_value: float | None = None
    max_value: float | None = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=1000000)
    release: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def observation_filter(self):
        if bool(self.quantity) != bool(self.unit):
            raise ValueError("quantity and unit must be supplied together; values use original units")
        if not self.quantity and any(v is not None for v in (self.min_value, self.max_value, self.statistic)):
            raise ValueError("numeric bounds/statistic require quantity and unit")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must not exceed max_value")
        if self.component_type and self.kind and self.kind != "component":
            raise ValueError("component_type requires kind=component")
        return self


def create_app(catalog=None, store=None):
    catalog = catalog or Catalog(json.loads(Path(os.environ.get("LEMONERGY_CATALOG", "api/catalog.json")).read_text()))
    store = store or AccessStore(os.environ.get("LEMONERGY_DATABASE_URL"))
    app = FastAPI(
        title="Lemonergy Battery Data API", version="1.0.0",
        description=("Paid hosted access to the free Lemonergy engineering library. "
                     "Search accepted records and retain every source, unit and measurement condition. "
                     "Monthly allowances count successful data requests, not downloaded records. "
                     f"The underlying data remains free at {REPOSITORY}."),
        license_info={"name": "Code: AGPL-3.0-or-later; data: CC BY 4.0", "url": REPOSITORY},
        swagger_ui_parameters={"persistAuthorization": False}, redoc_url=None,
    )
    log = logging.getLogger("lemonergy_api")

    def metadata():
        return {"provider": "Lemonergy", "release": catalog.release, "source_revision": catalog.revision,
                "data_license": "CC-BY-4.0", "free_library": REPOSITORY,
                "api_guide": f"{REPOSITORY}/blob/main/docs/10-hosted-api.md"}

    def error(status, code, message, headers=None):
        return JSONResponse({"error": {"code": code, "message": message}}, status_code=status,
                            headers={"Cache-Control": "no-store", **(headers or {})})

    @app.exception_handler(AccessError)
    async def access_error(request, exc):
        return error(exc.status, exc.code, exc.message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo input: a caller may accidentally put a credential in a URL.
        return error(422, "invalid_parameters", "Invalid query parameters. See /docs for allowed fields and ranges.")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return error(exc.status_code, "request_failed", str(exc.detail), exc.headers)

    @app.exception_handler(psycopg.Error)
    async def database_error(request, exc):
        log.error("Database request failed (%s)", type(exc).__name__)
        return error(503, "service_unavailable", "The service is temporarily unavailable.", {"Retry-After": "5"})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        log.error("Request failed (%s)", type(exc).__name__)
        return error(500, "internal_error", "The request could not be completed.")

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def paid(key, operation, charge=True):
        # Construct/encode the response inside the transaction so encoding errors
        # don't consume allowance. A network disconnect after commit still counts.
        response, headers = store.run(key, lambda usage: JSONResponse(operation(usage)), charge=charge)
        response.headers.update(headers)
        return response

    @app.get("/", tags=["Service"])
    def info():
        return {"meta": metadata(), "service": "Paid API access; free underlying data",
                "docs": "/docs", "accepted_products": sum(catalog.counts.values()),
                "counts_by_kind": catalog.counts,
                "access": "Operator activates a customer account after payment. Pricing and public launch are not configured in this repository."}

    @app.get("/healthz", tags=["Service"])
    def health():
        store.health()
        return {"status": "ok", "release": catalog.release}

    def listing(request, query, key, batteries=False, components=False):
        def operation(usage):
            if query.release and query.release != catalog.release:
                raise HTTPException(409, "Catalog release changed. Restart pagination with the current release.")
            if components:
                if query.kind and query.kind != "component":
                    raise HTTPException(422, "This endpoint only returns components.")
                query.kind = "component"
            rows = catalog.select(query, batteries_only=batteries)
            params = query.model_dump(exclude_none=True)
            params.update(release=catalog.release, offset=query.offset + query.limit)
            next_link = f"{request.url.path}?{urlencode(params)}" if query.offset + query.limit < len(rows) else None
            return {"meta": {**metadata(), "total": len(rows), "limit": query.limit, "offset": query.offset},
                    "data": [catalog.summary(r) for r in rows[query.offset:query.offset + query.limit]],
                    "links": {"next": next_link}}
        return paid(key, operation)

    @app.get("/v1/products", tags=["Catalog"])
    def products(request: Request, query: Annotated[ProductQuery, Query()], key: ApiKey):
        """Search accepted products. Numeric filters match ONE observation, in its original unit.

        Matching a value does not imply equivalent test conditions. Read the detail
        endpoint before comparing ratings. Page order is product UID ascending.
        """
        return listing(request, query, key)

    @app.get("/v1/batteries", tags=["Catalog"])
    def batteries(request: Request, query: Annotated[ProductQuery, Query()], key: ApiKey):
        """Cells, primary cells, modules, packs and systems; accepted contributions only."""
        return listing(request, query, key, batteries=True)

    @app.get("/v1/components", tags=["Catalog"])
    def components(request: Request, query: Annotated[ProductQuery, Query()], key: ApiKey):
        """Accepted electrical components. Pending review candidates are excluded."""
        return listing(request, query, key, components=True)

    @app.get("/v1/products/{uid:path}", tags=["Catalog"])
    def product(uid: str, key: ApiKey):
        """Full contribution, including every observation, bounds, conditions and evidence locator."""
        def operation(usage):
            data = catalog.detail(uid)
            if data is None:
                raise HTTPException(404, "Accepted product not found.")
            return {"meta": metadata(), "data": data}
        return paid(key, operation)

    @app.get("/v1/manufacturers", tags=["Catalog"])
    def manufacturers(key: ApiKey):
        counts = Counter(r["record"]["product"]["manufacturer"] for r in catalog.entries)
        return paid(key, lambda _: {"meta": metadata(), "data": [
            {"name": name, "accepted_products": count} for name, count in sorted(counts.items())]})

    @app.get("/v1/usage", tags=["Account"])
    def usage(key: ApiKey):
        """Own account only. Does not consume monthly allowance; the minute limit still applies."""
        return paid(key, lambda u: {"meta": metadata(), "data": u}, charge=False)

    return app
