# Azure Standard API Reference

> **Unofficial / Reverse-Engineered API**  
> Base URL: `https://api.azurestandard.com`  
> All responses are JSON. No API key required for public endpoints.

---

## Authentication

### `POST /login`

Authenticates a user and sets a session cookie.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response:** Sets `Set-Cookie: id=<token>; Domain=.azurestandard.com; Secure; HttpOnly`

**Notes:**
- The `id` cookie is the sole credential for all subsequent authenticated requests
- Pass it automatically via `withCredentials: true` (browser) or `Cookie: id=<token>` header (server-side)

---

### `GET /session`

Returns current session state. Use to verify a stored cookie is still valid.

**Auth required:** No (returns limited info when unauthenticated)

**Example unauthenticated response:**
```json
{
  "hyvorSso": {
    "userData": "e30=",
    "hash": "25e58aa22c23106c2fb7d8f8d7fcb241569f41564857559065402110ebd981dc"
  },
  "expires": "2036-08-21T10:28:18.422049-07:00"
}
```

**Authenticated response includes:** `person.email`, `person.order-place-issue`, `person.is-drop-coordinator`, `person.homeDeliveryDriverDropIds`, `person.homeDeliveryDriverCreditsTotal`

---

### `POST /logout`

Invalidates the current session.

---

## Drop Locations & Cutoff Dates

### `GET /drops`

Returns all active drop locations with their upcoming order cutoff schedules.

**Auth required:** No

**Query parameters:**
| Parameter | Type | Description |
|---|---|---|
| `limit` | integer | Max results per page (default: all) |

**Response fields:**
| Field | Type | Description |
|---|---|---|
| `id` | integer | Drop location ID |
| `name` | string | Drop location name |
| `geo.latitude` | float | Latitude |
| `geo.longitude` | float | Longitude |
| `active` | boolean | Whether drop is currently active |
| `exclusivity` | string | `"open"` (anyone can join) or `"private"` |
| `order-frequency` | array | List of upcoming order cycles |
| `order-frequency[].cutoff` | string | ISO date string (`YYYY-MM-DD`) — order cutoff date |
| `order-frequency[].orders` | integer | Number of orders for this cycle |
| `order-frequency[].homeDeliveryOrders` | array | Home delivery sub-orders for this cycle |

**Example response (truncated):**
```json
[
  {
    "id": 109,
    "name": "Dufur Market Drop",
    "geo": {
      "latitude": 45.453,
      "longitude": -121.13
    },
    "active": true,
    "exclusivity": "open",
    "order-frequency": [
      {
        "orders": 24,
        "homeDeliveryOrders": [],
        "cutoff": "2025-08-25"
      },
      {
        "orders": 22,
        "homeDeliveryOrders": [],
        "cutoff": "2025-09-01"
      }
    ]
  }
]
```

---

### `GET /drops/{id}`

Returns a single drop location with full cutoff schedule.

**Auth required:** No

**Parameters:** `id` — numeric drop ID

---

## Products & Catalogue

### `GET /products`

Returns product listings, filterable by category.

**Auth required:** No

**Query parameters:**
| Parameter | Type | Description |
|---|---|---|
| `categoryId` | integer | Filter by category (e.g. `21706` for canned vegetables) |
| `limit` | integer | Results per page |
| `offset` | integer | Pagination offset |

**Response fields per product:**
| Field | Type | Description |
|---|---|---|
| `id` | integer | Product ID |
| `name` | string | Product name |
| `slug` | string | URL slug |
| `isOrganic` | boolean | Organic certification |
| `isGeneticallyModified` | string | GMO status string |
| `storageClimate` | string | `"dry"`, `"refrigerated"`, `"frozen"` |
| `isShippableUps` | boolean | Whether product can ship via UPS |
| `treatAsActive` | boolean | Whether product is currently active/available |
| `brand.name` | string | Brand name |
| `countryOfOrigin` | string | Country of origin |
| `packaging` | array | Array of available package sizes |
| `packaging[].code` | string | Unique packaging code (e.g. `"TE815"`) |
| `packaging[].size` | string | Human-readable size (e.g. `"4 oz"`) |
| `packaging[].stock` | integer | Current stock level |
| `packaging[].price.retail.dollars` | float | Retail price |
| `packaging[].price.wholesale.dollars` | float | Wholesale/member price |
| `packaging[].images` | array | Image URLs |
| `packaging[].gtin13` | string | UPC/GTIN barcode |
| `packaging[].favorites` | integer | Number of users who favorited |

**Example response (single product):**
```json
{
  "id": 35206,
  "name": "Cranberry Orange Tea",
  "slug": "cranberry-orange-tea",
  "storageClimate": "dry",
  "isShippableUps": true,
  "isGeneticallyModified": "Not Genetically Modified",
  "isOrganic": false,
  "treatAsActive": false,
  "packaging": [
    {
      "code": "TE815",
      "size": "4 oz",
      "stock": 78,
      "price": {
        "retail": {
          "dollars": 13.99,
          "discount": "15%",
          "unit": "ounce",
          "dollars-per-unit": 3.4975
        },
        "wholesale": {
          "dollars": 11.45,
          "unit": "ounce",
          "dollars-per-unit": 2.8625
        }
      },
      "gtin13": "0603765375729",
      "favorites": 89
    }
  ],
  "brand": {
    "id": 2456,
    "name": "Abby's Elderberry",
    "slug": "abbys-elderberry",
    "url": "https://abbyselderberry.com"
  },
  "countryOfOrigin": "United States of America"
}
```

---

### `GET /products/{id}`

Returns full detail for a single product.

**Auth required:** No

---

## Account & Orders *(Auth Required)*

### `GET /person/{id}`

Returns account profile for the given person ID.

**Auth required:** Yes  
**Note:** Your account ID is in your Azure Standard account page URL.

**Key response fields:**
- Delivery addresses
- Assigned drop location
- Account flags (`order-place-issue`, `is-drop-coordinator`)

---

### `GET /ordered-packaged-products`

Returns all products the authenticated user has ever ordered, with order history metadata.

**Auth required:** Yes

**Key response fields:**
| Field | Description |
|---|---|
| `packaging.code` | Packaging code |
| `orderRecency` | Recency indicator |
| `quantity-ordered` | Total quantity ordered historically |
| `last-order-placed` | ISO date of most recent order containing this product |
| `packaging.next-purchase-arrival` | Expected arrival date if re-ordered now |
| `packaging.vendorShortedLastPurchase` | Whether vendor shorted the last purchase |

---

### `GET /orders/orders`

Returns the authenticated user's order history list.

**Auth required:** Yes

**Key response fields per order:**
- Order ID, status
- Cutoff date
- Trip/delivery date
- Order total
- Line item count

---

### `GET /order/{id}`

Returns full detail for a single order including all line items.

**Auth required:** Yes

---

## Shopping Lists *(Auth Required)*

### `GET /products/product_lists`

Returns all saved shopping lists for the authenticated user.

**Auth required:** Yes

**Response:** Array of list objects, each containing:
- `listUid` — unique list identifier
- `name` — list name
- `listItems` — array of product/packaging entries with quantities

---

### `GET /products/shop_product_lists`

Returns public/followed lists (community lists the user follows).

**Auth required:** Yes

---

## Account Financials *(Auth Required)*

### `GET /account-entries`

Returns account financial entries (credits, invoices, payments).

**Auth required:** Yes

**Query parameters:** `?` (check for pagination params)

---

### `GET /accounts_receivable/spend-metrics`

Returns spend summary metrics for the authenticated user.

**Auth required:** Yes

---

### `GET /accounts_receivable/pending-payments-state`

Returns any outstanding/pending payment state.

**Auth required:** Yes

---

## Other Endpoints Found in Source

| Endpoint | Notes |
|---|---|
| `GET /audit/product/{id}` | Product audit log |
| `GET /audit/packaged-product/{code}` | Packaging audit log |
| `GET /audit/products` | Products audit |
| `GET /_data-dropsNotClosed.geojson` | GeoJSON of all non-closed drops (map data) |
| `GET /_data-dropsClosed.geojson` | GeoJSON of closed drops |
| `POST /password/reset` | Password reset |
| `POST /password/confirm` | Password reset confirmation |

---

## Category IDs

Known category IDs discovered from the site URL structure:

| Category | ID |
|---|---|
| Canned Vegetables | `21706` |

> More category IDs can be discovered by browsing the Azure Standard shop and noting the numeric ID at the end of each category URL: `https://www.azurestandard.com/shop/category/{path}/{id}`
