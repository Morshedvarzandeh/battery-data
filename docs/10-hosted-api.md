# Lemonergy API for battery engineering tools

Use sourced battery information inside your own applications, selection tools
and engineering workflows. The Lemonergy API adds authenticated hosted access,
structured search and customer usage allowances to the free data library.

**Implementation status:** the paid-access service is implemented in this
repository. A public service URL, prices and automatic checkout are not yet
configured. The initial operating model is an agreed payment followed by
operator-issued access; this page does not offer a live subscription checkout.

## Choose how to use the library

| | Free GitHub library | Paid hosted API |
|---|---|---|
| Access | Browse and download public records | Customer API key and active paid access |
| Use | Research, inspect sources, reuse files | Query records from your own tools |
| Data | Accepted contributions, plus a clearly separate review queue | Accepted product contributions only |
| Evidence | Original units, conditions, source links and locators | The same full evidence in JSON |
| Updates | Pull the repository | A deployed catalog release, identified by content hash |
| Limits | No Lemonergy account required | Agreed monthly allowance and requests per minute |

The data remains free under the repository's existing CC BY 4.0 terms. Paying
covers the hosted service. Data downloaded from GitHub is not placed behind a
paywall. Manufacturer documents remain with their original publishers.

## API endpoints

The base URL is supplied when hosted customer access is provisioned. All `/v1/`
endpoints require the **`X-API-Key`** header. Send keys from a backend or private
script, never from a public website bundle or in a URL.

| Endpoint | Result |
|---|---|
| `GET /v1/batteries` | Rechargeable and primary cells, modules, packs and systems |
| `GET /v1/products` | All accepted products |
| `GET /v1/components` | Accepted contactors, fuses, precharge contactors, inverters, DC/DC converters and chargers |
| `GET /v1/products/{uid}` | Complete record, with every observation and its evidence |
| `GET /v1/manufacturers` | Manufacturers and accepted product counts |
| `GET /v1/usage` | Your account's allowance, usage and paid-through date |
| `GET /docs`, `/openapi.json` | Interactive documentation and API definition; no key required |
| `GET /`, `/healthz` | Service metadata and readiness; no key required |

At introduction, the snapshot contains 2,170 accepted battery products.
The 13 electrical components are still pending review, so the accepted component
endpoint is empty. Patent candidates are available in the free research library;
they are not exposed as accepted product data by this API.

## Python example

Set `LEMONERGY_API_BASE` to the service URL and `LEMONERGY_API_KEY` to your private
key in your execution environment. Do not commit them to Git.

```python
import os
import httpx

with httpx.Client(
    base_url=os.environ["LEMONERGY_API_BASE"],
    headers={"X-API-Key": os.environ["LEMONERGY_API_KEY"]},
    timeout=15,
) as client:
    response = client.get("/v1/batteries", params={"q": "INR21700-50E"})
    response.raise_for_status()
    product = response.json()["data"][0]["product"]
    response = client.get("/v1/products/" + product["uid"])
    response.raise_for_status()
    record = response.json()["data"]["record"]
    for observation in record["observations"]:
        print(observation["quantity"], observation["value"], observation["unit"],
              observation.get("conditions"), observation["locator"])
```

## Search and numeric filters

- `q`: case-insensitive text in manufacturer, model or product UID.
- `manufacturer`, `chemistry`: exact names, case-insensitive.
- `kind`: `cell`, `primary_cell`, `module`, `pack`, `system` or `component`.
- `component_type`: `contactor`, `precharge_contactor`, `fuse`, `inverter`,
  `dc_dc_converter` or `charger`.
- `quantity` and `unit`: supplied together, in the original recorded unit.
  Optional `statistic`, `min_value` and `max_value` narrow that observation.
- `limit`: 1–100, default 25. `offset`: nonnegative, default 0.

For example, `quantity=capacity&unit=mAh&statistic=rated&min_value=4500`
returns products with a matching rated capacity observation. It does not convert
Ah to mAh, combine two different observations, or imply that test conditions are
equivalent. Read the returned record's conditions before comparing values.

### Reproducible pagination

Products are ordered by UID. Follow `links.next`; it preserves filters and pins
`release` to the snapshot hash. A deployment with a different release returns
`409` instead of silently skipping or repeating products. Restart the search in
that case. Record links point to the exact source Git commit. Snapshots are
published with a service deployment, not changed in a running worker.

## Usage and errors

One successfully constructed data response consumes one monthly request,
regardless of record count. `/v1/usage` does not consume monthly allowance.
Successful account and data requests share a fixed UTC-minute rate limit. All
keys and workers share the same customer counters. Monthly usage resets on the
first day of each UTC calendar month; unused allowance does not carry forward.
A connection lost after the server commits a response still counts as a request.

`X-Monthly-Limit` and `X-Monthly-Remaining` show the monthly allowance.
`X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` describe the
current minute bucket; reset is a Unix timestamp. `429` responses include
`Retry-After` in seconds. Reduce request frequency before retrying.

| HTTP status | Meaning |
|---|---|
| 401 | Missing, invalid, revoked or expired key |
| 402 | Paid access has expired or has not been activated |
| 403 | Customer account is inactive |
| 404 | Accepted product or endpoint not found |
| 409 | Catalog release changed during pagination |
| 422 | Invalid filters, limits or query parameters |
| 429 | Rate or monthly allowance exhausted |
| 503 | Service temporarily unavailable; access fails closed |

Errors use `{"error":{"code":"…","message":"…"}}`. Failed requests do not
consume monthly allowance. Prices, support commitments and service guarantees
must be agreed separately; the repository does not assert an uptime SLA.

---

Maintained by **Lemonergy** · [Free battery library](../catalog/README.md) ·
[Component datasheets](../components/catalog.md) · [Operator setup](../api/README.md)
