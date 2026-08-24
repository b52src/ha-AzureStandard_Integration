#!/usr/bin/env python3
"""Probe real Azure Standard API endpoint paths after login.

Usage:
    .venv/bin/python3 probe_endpoints.py

Prompts for email + password, logs in, then tries every plausible URL
variant for orders, shopping lists, ordered products, and person profile.
Prints the HTTP status and first 300 chars of each response.
"""
from __future__ import annotations

import asyncio
import getpass
import json
import os
import sys

API_BASE = "https://api.azurestandard.com"
PERSON_ID = 1674720  # from /session response


async def main() -> None:
    import aiohttp

    print("Azure Standard — endpoint probe")
    print("=" * 40)
    email = os.environ.get("AZ_EMAIL") or input("Email: ").strip()
    password = os.environ.get("AZ_PASSWORD") or getpass.getpass("Password: ")

    jar = aiohttp.CookieJar(unsafe=True)
    headers = {
        "Origin": "https://www.azurestandard.com",
        "Referer": "https://www.azurestandard.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }

    async with aiohttp.ClientSession(cookie_jar=jar, headers=headers) as session:

        async def probe(path: str, full: bool = False) -> None:
            url = f"{API_BASE}{path}"
            try:
                async with session.get(url) as r:
                    body = await r.text()
                    try:
                        parsed = json.loads(body)
                        if full:
                            # For arrays show full first element; for dicts show all
                            if isinstance(parsed, list):
                                display = json.dumps(parsed[0] if parsed else [], indent=2, default=str)
                                print(f"  {r.status}  {path}  ({len(parsed)} items, showing first)")
                            else:
                                display = json.dumps(parsed, indent=2, default=str)
                                print(f"  {r.status}  {path}")
                            print(display)
                        else:
                            preview = json.dumps(parsed, default=str)[:300]
                            print(f"  {r.status}  {path}")
                            if r.status == 200:
                                print(f"       {preview}")
                    except Exception:
                        print(f"  {r.status}  {path}")
                        if r.status == 200:
                            print(f"       {body[:300]}")
            except aiohttp.ClientError as exc:
                print(f"  ERR  {path}  → {exc}")

        # Login
        print("\nLogging in …", end=" ", flush=True)
        async with session.post(
            f"{API_BASE}/login",
            json={"username": email, "password": password},
        ) as r:
            if r.status not in (200, 201):
                print(f"FAILED HTTP {r.status}")
                return
        print("OK ✓\n")

        DROP_ID = 2873

        # beehiveApiV2 = https://api.azurestandard.com/v2  (confirmed from JS)
        # Shopping lists live under /v2/products/product_lists
        CUSTOMER_NUM = "C1674720"
        print("--- Shopping lists (v2 API) ---")
        for path in [
            f"/v2/products/product_lists?customerNumber={CUSTOMER_NUM}",
            f"/v2/products/product_lists?customerNumber={PERSON_ID}",
            f"/v2/products/product_lists?filter-person={PERSON_ID}",
            "/v2/products/product_lists",
        ]:
            await probe(path, full=True)

        # Drop endpoint — /drops/{id} returned 404; try /v2 and other patterns
        print("\n--- Drop detail ---")
        for path in [
            f"/v2/drops/{DROP_ID}",
            f"/drops?id={DROP_ID}",
            f"/drops?filter-drop={DROP_ID}",
            # The drop-memberships endpoint returned drop=2873 — does membership include cutoff?
            f"/drop-memberships?filter-person={PERSON_ID}&inline=drop",
            # Trip endpoint — order had trip=64544
            "/trips/64544",
            "/trip/64544",
        ]:
            await probe(path, full=True)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
