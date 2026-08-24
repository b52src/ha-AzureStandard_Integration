# API Research Notes

Raw notes from reverse-engineering the Azure Standard website API.  
Research date: August 2025

---

## Discovery Method

The Azure Standard website (`azurestandard.com`) is a single-page application built on AngularJS 1.8. All data is fetched from `https://api.azurestandard.com` via XHR calls. The API base URL is embedded in the site's bootstrap JavaScript:

```javascript
apiHost: "https://api.azurestandard.com"
```

The JavaScript bundles were downloaded and analyzed:
- `https://www.azurestandard.com/core/core.b0bc7c14.js` (~257 KB)
- `https://www.azurestandard.com/modules/modules.3f425a54.js` (~89 KB)

---

## Authentication Mechanism

Found in JS source: all authenticated API calls use `withCredentials: true`, which sends session cookies automatically. Cookie-based auth confirmed:

```javascript
// From modules JS
withCredentials: true, headers: j
// ...
l.orderedPackagedProducts = { method: ..., withCredentials: true, headers: j }
```

The site also references cookie names:
- `id` — session identity cookie (checked by `document.cookie.indexOf("; id=") >= 0`)
- `price_pref` — pricing preference
- `customer` — customer flag
- `asrec`, `asfre`, `asmon` — analytics/tracking cookies

The session endpoint (`GET /session`) was confirmed live:
```http
GET https://api.azurestandard.com/session
→ HTTP 200
→ Sets: price_pref, customer, asrec, asfre, asmon cookies
```

Login endpoint found in JS: `c = { login: { url: ... } }` with `signIn` function, `POST /login`.

---

## Endpoint Discovery

Endpoints were extracted from the JS bundles using regex pattern matching for string literals containing API path keywords (order, cart, list, person, session, drop, account, product, favor, deliver, payment, address).

### Confirmed live (unauthenticated):

```
GET https://api.azurestandard.com/drops
GET https://api.azurestandard.com/drops?limit=5
GET https://api.azurestandard.com/products?categoryId=21706&limit=5
GET https://api.azurestandard.com/session
```

### Confirmed requiring auth (return empty or error unauthenticated):

```
GET /orders
GET /lists
GET /cart
GET /orders/orders
GET /products/product_lists
GET /products/shop_product_lists
GET /ordered-packaged-products
GET /person/{id}
GET /account-entries
GET /accounts_receivable/spend-metrics
GET /accounts_receivable/pending-payments-state
GET /accounts_receivable/validate-ach
```

---

## Live Drop Data Sample

Confirmed live data from `GET /drops?limit=2`:

```json
{
  "id": 109,
  "name": "Dufur Market Drop",
  "geo": { "latitude": 45.453, "longitude": -121.13 },
  "active": true,
  "exclusivity": "open",
  "order-frequency": [
    { "orders": 24, "homeDeliveryOrders": [], "cutoff": "2025-08-25" },
    { "orders": 22, "homeDeliveryOrders": [], "cutoff": "2025-09-01" },
    { "orders": 26, "homeDeliveryOrders": [], "cutoff": "2025-09-08" },
    { "orders": 38, "homeDeliveryOrders": [], "cutoff": "2025-09-15" }
  ]
}
```

Cutoff dates are weekly (every Monday) extending ~6 months into the future.

---

## Live Product Data Sample

Confirmed live data from `GET /products?categoryId=21706&limit=1`:

```json
{
  "id": 35206,
  "name": "Cranberry Orange Tea",
  "storageClimate": "dry",
  "isShippableUps": true,
  "isGeneticallyModified": "Not Genetically Modified",
  "isOrganic": false,
  "treatAsActive": false,
  "packaging": [{
    "code": "TE815",
    "size": "4 oz",
    "stock": 78,
    "price": {
      "retail": { "dollars": 13.99, "discount": "15%", "unit": "ounce", "dollars-per-unit": 3.4975 },
      "wholesale": { "dollars": 11.45, "unit": "ounce", "dollars-per-unit": 2.8625 }
    },
    "gtin13": "0603765375729",
    "favorites": 89,
    "trustpilotNumberOfReviews": 2,
    "trustpilotStarsAverage": 4.5
  }],
  "brand": { "id": 2456, "name": "Abby's Elderberry" },
  "countryOfOrigin": "United States of America"
}
```

---

## Interesting JS String Literals Found

Key data field names extracted from the JavaScript source that reveal the shape of authenticated responses:

```
packaging.next-purchase-arrival          # Expected arrival date if re-ordered
packaging.vendorShortedLastPurchase      # Whether vendor shorted last purchase
packaging.next-purchase-arrival-timestamp
packaging.bargain-bin-notes
orderRecency                             # Order recency indicator
quantity-ordered                         # Total qty ordered historically
last-order-placed                        # Date last ordered
first-order-placed                       # Date first ordered
quantity-shipped                         # Qty actually shipped
order-line                               # Order line reference
deliveredToDrop                          # Delivery to drop flag
deliveredToHome                          # Home delivery flag
listQuantitiesByCode                     # Quantities per packaging code in list
listUid                                  # Unique list identifier
```

---

## Event Names (AngularJS Event Bus)

These reveal the real-time state model:

```
order:created       # New order created
order:changed       # Order modified
order:deleted       # Order deleted
orderLine:created   # Line item added
orderLine:changed   # Line item modified
orderLine:deleted   # Line item removed
session:loggedIn    # User logged in
session:loggedOut   # User logged out
session:registered  # New registration
drop:changed        # Drop selection changed
person:changed      # Profile updated
```

---

## Algolia Search

The site uses Algolia (`j8n8i8ke2y-dsn.algolia.net`) for product search. This is separate from the REST API and would require an Algolia API key (embedded in the JS) for integration. Not planned for initial implementation — the REST API product/category endpoints are sufficient.

---

## Image CDN

Product images are served from:
- `https://img.azurestandard.com` — Imgix-powered image CDN with dynamic resizing
- `https://media.azurestandard.com` — Original media storage

Image URL pattern: `https://img.azurestandard.com/unsafe/fit-in/282x216/filters:fill(white)/{image_path}`

---

## Notes on Rate Limiting

No rate limiting was observed during research. The API is protected behind Cloudflare (confirmed via `cf-ray` response header and Cloudflare IP ranges). Standard Cloudflare bot mitigation is in place but did not trigger during testing with normal `curl` requests.

**Recommended polling limits for the HA integration:**
- Never poll faster than every 30 minutes for auth-required endpoints
- Public endpoints (drops, products) can safely poll every 6 hours
- Treat any HTTP 429 or 503 response with exponential backoff
