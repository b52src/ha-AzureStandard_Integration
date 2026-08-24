#!/usr/bin/env python3
"""Quick credential / API smoke-test for the Azure Standard integration.

Usage (interactive):
    .venv/bin/python3 test_credentials.py

Usage (non-interactive, e.g. CI or headless):
    AZ_EMAIL=you@example.com AZ_PASSWORD=secret .venv/bin/python3 test_credentials.py

Requires:  aiohttp  (already installed in .venv)
"""
from __future__ import annotations

import asyncio
import getpass
import json
import os
import sys

API_BASE = "https://api.azurestandard.com"
API_V2 = "https://api.azurestandard.com/v2"


async def main() -> None:
    try:
        import aiohttp
    except ImportError:
        print("ERROR: aiohttp not found. Run:  .venv/bin/pip install aiohttp")
        sys.exit(1)

    print("Azure Standard — credential smoke-test")
    print("=" * 40)

    email = os.environ.get("AZ_EMAIL") or input("Email: ").strip()
    password = os.environ.get("AZ_PASSWORD") or getpass.getpass("Password: ")

    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar) as session:

        async def get(url: str, params: dict | None = None):
            async with session.get(url, params=params) as r:
                r.raise_for_status()
                return await r.json()

        async def post(path: str, payload: dict):
            async with session.post(f"{API_BASE}{path}", json=payload) as r:
                r.raise_for_status()
                return await r.json()

        # 1 — Login
        print("\n[1] POST /login …", end=" ", flush=True)
        try:
            await post("/login", {"username": email, "password": password})
            print("OK ✓")
        except aiohttp.ClientResponseError as exc:
            if exc.status in (401, 403):
                print("FAILED — invalid email or password")
            else:
                print(f"FAILED — HTTP {exc.status}")
            return
        except aiohttp.ClientError as exc:
            print(f"NETWORK ERROR — {exc}")
            return

        cookie_value = next((c.value for c in jar if c.key == "id"), "")
        print(f"    Session cookie: {'present ✓' if cookie_value else 'MISSING ✗'}")

        # 2 — Session: extract personId
        print("\n[2] GET /session …", end=" ", flush=True)
        person_id: int | None = None
        try:
            sess = await get(f"{API_BASE}/session")
            # Confirmed: "person" is an int, not a dict
            raw = sess.get("personId") or sess.get("person")
            person_id = int(raw) if raw else None
            print(f"OK ✓  personId={person_id}")
        except aiohttp.ClientError as exc:
            print(f"FAILED — {exc}")

        if not person_id:
            print("Cannot continue without a person ID.")
            return

        # 3 — Drop membership
        print(f"\n[3] GET /drop-memberships?filter-person={person_id} …", end=" ", flush=True)
        drop_id: int | None = None
        try:
            membership = await get(
                f"{API_BASE}/drop-memberships", params={"filter-person": person_id}
            )
            if isinstance(membership, list) and membership:
                drop_id = int(membership[0]["drop"])
            elif isinstance(membership, dict):
                drop_id = int(membership["drop"])
            print(f"OK ✓  drop_id={drop_id}")
            print(json.dumps(membership, indent=2, default=str))
        except aiohttp.ClientError as exc:
            print(f"FAILED — {exc}")

        # 4 — Drop from public list (paginated, max 200/page)
        if drop_id:
            print(f"\n[4] GET /drops (paginated scan for drop {drop_id}) …", end=" ", flush=True)
            try:
                match = None
                start = 0
                while match is None:
                    page = await get(f"{API_BASE}/drops", params={"limit": 200, "start": start})
                    if not isinstance(page, list) or not page:
                        break
                    match = next((d for d in page if isinstance(d, dict) and d.get("id") == drop_id), None)
                    if match or len(page) < 200:
                        break
                    start += 200
                if match:
                    print(f"OK ✓  name={match.get('name')}")
                    print("order-frequency sample:")
                    print(json.dumps((match.get("order-frequency") or [])[:2], indent=2, default=str))
                else:
                    print(f"Drop {drop_id} not found in paginated /drops list ✗")
            except aiohttp.ClientError as exc:
                print(f"FAILED — {exc}")

        # 5 — Orders
        print(f"\n[5] GET /orders?filter-person={person_id}&limit=5 …", end=" ", flush=True)
        try:
            orders = await get(
                f"{API_BASE}/orders", params={"filter-person": person_id, "limit": 5}
            )
            print(f"OK ✓  {len(orders)} order(s)")
            if orders:
                print("First order (raw):")
                print(json.dumps(orders[0], indent=2, default=str))
        except aiohttp.ClientError as exc:
            print(f"FAILED — {exc}")

        # 6 — Ordered products (purchase history)
        ordered_products = []
        print(f"\n[6] GET /person/{person_id}/ordered-packaged-products …", end=" ", flush=True)
        try:
            ordered_products = await get(f"{API_BASE}/person/{person_id}/ordered-packaged-products")
            print(f"OK ✓  {len(ordered_products)} product(s) in history")
            if ordered_products:
                print("First product (raw):")
                print(json.dumps(ordered_products[0], indent=2, default=str))
        except aiohttp.ClientError as exc:
            print(f"FAILED — {exc}")

        # 7 — Account balance
        print(f"\n[7] GET /account-entries (balance) …", end=" ", flush=True)
        try:
            entries = await get(
                f"{API_BASE}/account-entries",
                params={"filter-person": person_id, "balance": "true", "limit": 1, "start": -1},
            )
            print(f"OK ✓")
            print(json.dumps(entries, indent=2, default=str))
        except aiohttp.ClientError as exc:
            print(f"FAILED — {exc}")

        # 8 — Shopping lists (metadata)
        print(f"\n[8] GET /v2/products/product_lists?customerNumber={person_id} …", end=" ", flush=True)
        product_lists = []
        try:
            product_lists = await get(
                f"{API_V2}/products/product_lists",
                params={"customerNumber": person_id},
            )
            print(f"OK ✓  {len(product_lists)} list(s)")
            for lst in product_lists[:3]:
                print(f"  list id={lst.get('id')}  name={lst.get('name')}")
        except aiohttp.ClientResponseError as exc:
            print(f"FAILED — HTTP {exc.status}")
        except aiohttp.ClientError as exc:
            print(f"FAILED — {exc}")

        # 9 — Items for first list
        if product_lists:
            first_list_id = product_lists[0].get("id")
            print(f"\n[9] GET /v2/products/product_lists/{first_list_id}/items …", end=" ", flush=True)
            try:
                items = await get(f"{API_V2}/products/product_lists/{first_list_id}/items")
                print(f"OK ✓  {len(items)} item(s)")
                if items:
                    print("First item (raw):")
                    print(json.dumps(items[0], indent=2, default=str))
            except aiohttp.ClientError as exc:
                print(f"FAILED — {exc}")

        # 10 — Product discovery engine (offline — no network call)
        print("\n[10] ProductDiscoveryEngine.analyze() …", end=" ", flush=True)
        if not ordered_products:
            print("SKIPPED — no ordered-products data from check [6]")
        else:
            try:
                import sys as _sys
                import os as _os
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location(
                    "discovery",
                    _os.path.join(_os.path.dirname(__file__), "custom_components", "azure_standard", "discovery.py"),
                )
                _mod = _ilu.module_from_spec(_spec)
                _sys.modules["discovery"] = _mod
                _spec.loader.exec_module(_mod)
                ProductDiscoveryEngine = _mod.ProductDiscoveryEngine
                engine = ProductDiscoveryEngine(min_purchase_count=3)
                stats = engine.analyze(ordered_products)
                candidates = [s for s in stats if s.is_candidate]
                suggestions = engine.get_new_suggestions(stats, already_tracked=set())
                print(
                    f"OK ✓  {len(stats)} stats parsed, "
                    f"{len(candidates)} candidates (>=3 orders), "
                    f"{len(suggestions)} new suggestions"
                )
                if stats:
                    top = stats[0]
                    print(
                        f"    Top product: code={top.code}  order_count={top.order_count}"
                        f"  last_ordered={top.last_ordered}"
                        f"  days_since={top.days_since_last_order}"
                    )
            except Exception as exc:
                print(f"FAILED — {exc}")
                import traceback
                traceback.print_exc()

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
