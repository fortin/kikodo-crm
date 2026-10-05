# Kikodo CRM - API Documentation

Live surface from Django REST Framework, MCP, OAuth, and session AJAX. There is no OpenAPI/Swagger file in the repo. For a compact reference, see also [`Kikodo CRM API spec.md`](./Kikodo%20CRM%20API%20spec.md).

## Overview

The API covers:

- **CRM REST** at `/api/` — companies, contacts, deals, activities, tags, pipelines
- **Analytics REST** at `/analytics/api/` — dashboards, metrics, reports, Airtable-style bases
- **Public REST** — config, token auth, newsletter subscribe
- **Session AJAX** — in-app AI chat / enrich / brief
- **MCP** — tool calling over HTTP/SSE (and the same tools in the in-app AI assistant)

## Conventions

| Item | Behavior |
| --- | --- |
| **Base URL** | Site root (e.g. `http://localhost:8000`), **not** `/crm/` |
| **Format** | JSON (`Content-Type: application/json`) |
| **Trailing slashes** | Required (DRF `DefaultRouter`) |
| **List envelope** | `{ "count", "next", "previous", "results" }` |
| **Pagination** | `?page=` — default **20** per page. No `page_size` override is configured |
| **Search** | `?search=` (not `field__icontains` query params) |
| **Exact filters** | Only the `filterset_fields` listed per resource |
| **Sort** | `?ordering=field` or `?ordering=-field` |
| **CRUD** | Every ViewSet is a full `ModelViewSet`: `GET/POST` collection, `GET/PUT/PATCH/DELETE` detail |
| **Auth (REST)** | Session cookie **or** `Authorization: Token <key>` |
| **Default permission** | `IsAuthenticated` except the public endpoints below |
| **Throttling** | Disabled |
| **CSRF** | Required for session-auth mutating requests; not required for Token auth |

Example list URL:

```
GET http://localhost:8000/api/contacts/?page=2&search=jane&ordering=-created_at
```

---

## Authentication

### Token Authentication (recommended for integrations)

Obtain a token:

```http
POST /api/token/
Content-Type: application/json

{ "username": "...", "password": "..." }
```

**200:** `{ "token": "<key>" }`  
**400:** missing fields · **401:** invalid credentials  

Use on subsequent requests:

```
Authorization: Token <key>
```

### Session Authentication

Browser login / session cookies work on all authenticated REST routes. Include the CSRF token for `POST` / `PUT` / `PATCH` / `DELETE` when using sessions.

---

## Public REST

### `GET /api/config/`

No auth. Intended for extensions (e.g. SalesNav exporter).

```json
{ "base_url": "https://example.com", "api_url": "https://example.com/api" }
```

`base_url` comes from Django `BASE_URL` (values may be `null` if unset).

### `POST /api/newsletter/subscribe/`

```json
{ "name": "First Last", "email": "user@example.com" }
```

- `email` required, must contain `@`
- `name` split on first space → `first_name` / `last_name`
- Upserts `Contact` by email: `newsletter_subscribed=true`, `can_marketing_email=true`, `source=newsletter_signup`
- Starts welcome automation if not already enrolled

**201** new contact / **200** existing: `{ "status": "subscribed", "contact_id": <id> }`  
**400:** `{ "error": "email is required" }` or `"invalid email"`

---

## CRM REST (`/api/`)

Router root: `GET /api/`. Nested objects are expanded on **read**; write FKs use `*_id` fields. `owner` is **read-only** on companies, contacts, deals, and activities.

### Companies — `/api/companies/`

**Filters:** `industry`, `is_active`, `owner`  
**Search:** `name`, `email`, `industry`, `phone`, `city`, `state`  
**Order:** `name` (default), `created_at`, `annual_revenue`

| Field | Notes |
| --- | --- |
| `id`, `name`, `industry`, `website`, `phone`, `email` | |
| `address`, `city`, `state`, `country`, `postal_code`, `full_address` | `full_address` read-only |
| `description`, `annual_revenue`, `employee_count`, `size_category`, `facility_count` | |
| `linkedin_url`, `priority_tier` | `priority_tier`: `1`, `2`, `3` |
| `owner` | nested `{id, username, first_name, last_name, email}` |
| `is_active`, `created_at`, `updated_at` | timestamps read-only |

```http
GET /api/companies/
POST /api/companies/
GET /api/companies/{id}/
PUT|PATCH /api/companies/{id}/
DELETE /api/companies/{id}/
GET /api/companies/stats/
```

**`GET /api/companies/stats/`**

```json
{
  "total_companies": 0,
  "active_companies": 0,
  "industry_breakdown": [{ "industry": "...", "count": 0 }]
}
```

### Contacts — `/api/contacts/`

**Filters:** `status`, `is_active`, `owner`, `company`  
**Search:** `first_name`, `last_name`, `email`, `phone`, `company__name`  
**Order:** `last_name`, `first_name` (default), `created_at`

`status`: `lead` | `prospect` | `customer` | `inactive`  
`salutation`: `Mr.` | `Mrs.` | `Ms.` | `Dr.` | `Prof.` (and blank)

| Field | Notes |
| --- | --- |
| `id`, `salutation`, `first_name`, `last_name`, `full_name` | `full_name` read-only |
| `email`, `phone`, `mobile`, `job_title`, `department` | |
| `company` | nested company on read |
| `company_id` | write-only, optional |
| `address`, `city`, `state`, `country`, `postal_code`, `full_address` | |
| `status`, `source`, `notes`, `is_active` | |
| `linkedin_url`, `twitter_handle` | |
| `owner`, `created_at`, `updated_at` | |

Serializer does **not** expose many model fields (e.g. `outreach_status`, newsletter flags, `bio`, `headline`).

```http
GET /api/contacts/
POST /api/contacts/
GET /api/contacts/{id}/
PUT|PATCH /api/contacts/{id}/
DELETE /api/contacts/{id}/
GET /api/contacts/stats/
```

**Create example**

```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane.smith@example.com",
  "phone": "+1234567891",
  "job_title": "Marketing Director",
  "company_id": 2,
  "status": "lead"
}
```

**`GET /api/contacts/stats/`**

```json
{
  "total_contacts": 0,
  "active_contacts": 0,
  "recent_contacts": 0,
  "status_breakdown": [{ "status": "lead", "count": 0 }]
}
```

`recent_contacts` = created in the last 30 days.

### Deals — `/api/deals/`

**Filters:** `stage`, `priority`, `is_active`, `owner`, `contact`, `company`  
**Search:** `name`, `contact__first_name`, `contact__last_name`, `company__name`  
**Order:** `-expected_close_date` (default), `name`, `amount`, `created_at`

`stage`: `prospecting` | `qualification` | `proposal` | `negotiation` | `closed_won` | `closed_lost`  
`priority`: `low` | `medium` | `high`

| Field | Notes |
| --- | --- |
| `id`, `name`, `description`, `amount`, `currency` | `contact_id` **required** on create |
| `stage`, `probability`, `priority` | |
| `contact` / `contact_id`, `company` / `company_id` | nested on read |
| `expected_close_date`, `actual_close_date`, `notes`, `is_active` | |
| `weighted_amount`, `days_to_close` | read-only |
| `owner`, `created_at`, `updated_at` | |

`pipeline` / `pipeline_stage` FKs are **not** in the serializer.

```http
GET /api/deals/
POST /api/deals/
GET /api/deals/{id}/
PUT|PATCH /api/deals/{id}/
DELETE /api/deals/{id}/
GET /api/deals/pipeline/
GET /api/deals/stats/
```

**`GET /api/deals/pipeline/`** — grouped by `stage`: `count`, `total_amount`, `weighted_amount`

**`GET /api/deals/stats/`**

```json
{
  "total_deals": 0,
  "active_deals": 0,
  "recent_deals": 0,
  "total_pipeline": 0,
  "weighted_pipeline": 0,
  "stage_breakdown": [{ "stage": "...", "count": 0, "total_amount": 0 }]
}
```

### Activities — `/api/activities/`

**Filters:** `activity_type`, `status`, `owner`, `contact`, `company`, `deal`  
**Search:** `subject`, `description`, `contact__first_name`, `contact__last_name`  
**Order:** `-due_date`, `-created_at` (default), `subject`

`activity_type`: `call` | `email` | `meeting` | `task` | `note` | `demo` | `proposal` | `linkedin` | `system`  
`status`: `pending` | `sent` | `cancelled` | `completed`

| Field | Notes |
| --- | --- |
| `id`, `activity_type`, `subject`, `description`, `status` | |
| `contact` / `contact_id`, `company` / `company_id`, `deal` / `deal_id` | optional FKs |
| `due_date`, `completed_date`, `duration_minutes`, `outcome` | `completed_date` read-only |
| `owner`, `created_at`, `updated_at` | |

Not serialized: `direction`, `link`, threading, delivery fields, etc.

```http
GET /api/activities/
POST /api/activities/
GET /api/activities/{id}/
PUT|PATCH /api/activities/{id}/
DELETE /api/activities/{id}/
GET /api/activities/upcoming/
GET /api/activities/stats/
```

**`GET /api/activities/upcoming/`** — up to 20 with `due_date >= now` and `status=pending`  
**`GET /api/activities/stats/`** — totals, completed/pending, last-30-day count, `type_breakdown`

### Tags — `/api/tags/`

**Search:** `name`, `description` · **Order:** `name`  
Fields: `id`, `name`, `color`, `description`

### Pipelines — `/api/pipelines/`

**Search:** `name`, `description` · **Order:** `name`, `created_at`  
Fields: `id`, `name`, `description`, `is_default`, `is_active`, `created_at`, `updated_at`

### Pipeline stages — `/api/pipeline-stages/`

**Filter:** `pipeline` · **Search:** `name`, `pipeline__name` · **Order:** `pipeline`, `order`  
Write: `pipeline_id` required on create.  
Fields: `id`, `pipeline`, `pipeline_id`, `name`, `order`, `probability`, `is_closed`, `is_won`, timestamps

### Tag links

| Resource | Filters | Write |
| --- | --- | --- |
| `/api/contact-tags/` | `contact`, `tag` | `contact_id`, `tag_id` |
| `/api/company-tags/` | `company`, `tag` | `company_id`, `tag_id` |
| `/api/deal-tags/` | `deal`, `tag` | `deal_id`, `tag_id` |

Read returns nested parent + tag.

---

## Analytics REST (`/analytics/api/`)

Same auth, pagination, and CRUD pattern. `created_by` / `user` are set from the request user on create where noted.

| Collection | Filters | Extra |
| --- | --- | --- |
| `/analytics/api/dashboard-widgets/` | `widget_type`, `is_active`, `user` | search `name`, `description` |
| `/analytics/api/reports/` | `report_type`, `is_public`, `is_active`, `created_by` | sets `created_by` |
| `/analytics/api/sales-goals/` | `goal_type`, `period_type`, `is_active`, `user` | sets `user` |
| `/analytics/api/activity-summaries/` | `date`, `user` | |
| `/analytics/api/pipeline-snapshots/` | `date`, `stage` | |
| `/analytics/api/contact-engagement/` | `date`, `contact` | |
| `/analytics/api/deal-forecasts/` | `forecast_date`, `confidence_level` | |
| `/analytics/api/custom-fields/` | `field_type`, `entity_type`, `is_required`, `is_active` | |
| `/analytics/api/custom-field-values/` | `custom_field`, `content_type` | write `custom_field_id` |
| `/analytics/api/dashboard-templates/` | `period_type`, `is_active`, `is_public`, `created_by` | **`AllowAny`** (testing) |
| `/analytics/api/custom-metrics/` | `template`, `metric_type`, `period` | |
| `/analytics/api/metric-data-points/` | `metric__template`, `date_recorded` | |
| `/analytics/api/dashboard-views/` | `template`, `chart_type`, `is_default`, `is_public`, `created_by` | |
| `/analytics/api/bases/` | `is_active`, `is_public`, `created_by`, `color` | |
| `/analytics/api/tables/` | `base`, `is_active`, `color`, `default_view` | |
| `/analytics/api/table-fields/` | `table`, `field_type`, `is_primary`, `is_required` | |
| `/analytics/api/records/` | `table` | `data` must be a JSON object |

### Custom actions

- `POST /analytics/api/dashboard-templates/{id}/import_csv/` — multipart `csv_file`
- `GET /analytics/api/custom-metrics/{id}/progress_summary/`
- `GET /analytics/api/bases/{id}/tables/`
- `GET /analytics/api/tables/{id}/records/`
- `GET /analytics/api/tables/{id}/fields/`
- `PATCH /analytics/api/records/{id}/update_field/` — `{ "field_name", "field_value" }`

### Serializer fields (analytics)

- **Widget:** `name`, `widget_type`, `description`, `config`, `order`, `is_active`, `user`, timestamps
- **Report:** `name`, `description`, `report_type`, `filters`, `columns`, `created_by`, `is_public`, `is_active`
- **Sales goal:** `name`, `goal_type`, `period_type`, `target_value`, `currency`, `start_date`, `end_date`, `user`, `is_active`
- **Activity summary:** `date`, `user`, `calls_made`, `emails_sent`, `meetings_held`, `tasks_completed`, `notes_added`, `deals_created`, `deals_closed_won`, `deals_closed_lost`, `revenue_closed`, `contacts_created`, `companies_created`
- **Pipeline snapshot:** `date`, `stage`, `count`, `total_value`, `weighted_value`
- **Contact engagement:** `contact`, `date`, `email_opens`, `email_clicks`, `website_visits`, `social_interactions`, `activities_count`, `last_activity_date`
- **Deal forecast:** `deal`, `forecast_date`, `forecasted_amount`, `probability`, `confidence_level`, `notes`
- **Custom field:** `name`, `field_type`, `entity_type`, `label`, `description`, `is_required`, `is_active`, `options`, `order`
- **Custom field value:** `custom_field`, `content_type`, `object_id`, `text_value`, `number_value`, `date_value`, `boolean_value`, `json_value`
- **Dashboard template:** `name`, `description`, `csv_template`, `created_by`, `is_active`, `is_public`, `period_type`, `metrics_count`
- **Custom metric:** `template`, `metric_name`, `description`, `target_value`, `actual_value`, `period`, `period_start_date`, `period_end_date`, `metric_type`, `unit`, `percentage_achieved`, `is_on_track`
- **Metric data point:** `metric`, `value`, `date_recorded`, `notes`
- **Dashboard view:** `template`, `name`, `description`, `configuration`, `chart_type`, `is_default`, `is_public`
- **Base / table / field / record:** as in serializers (`icon`, `color`, `data`, etc.)

**Import CSV success response**

```json
{
  "message": "CSV imported successfully",
  "created_count": 10,
  "updated_count": 2,
  "warnings": []
}
```

---

## Session AJAX (login required, not Token REST)

All `POST`. CSRF + session cookie.

### `POST /ai/chat/`

```json
{ "message": "…", "messages": [ { "role": "user"|"assistant", "content": "…" } ] }
```

```json
{ "ok": true, "response": "…", "messages": […], "error": null, "backend": "…" }
```

**400** if body is not JSON or `message` is empty. The chat loop uses the same tool set as MCP (including create company/contact/deal).

### `POST /ai/contact/{id}/enrich/`

```json
{ "ok": true, "updated": true, "message": "…", "reload": true }
```

or `{ "ok": false, "error": "…" }`

### `POST /ai/company/{id}/brief/`

```json
{ "ok": true, "brief": "<markdown>" }
```

HTML UI routes (`/contacts/`, `/deals/`, newsletters, signals, etc.) are not a JSON API.

**Not in REST:** signals, pain signals, sequences, newsletters (except public subscribe), welcome automations — use MCP or the UI.

---

## MCP

Mounted at `/mcp` in `kikodo_crm/asgi.py` (typically run with uvicorn on port **8081**). The same tools are available to the in-app AI chat.

| Transport | URL |
| --- | --- |
| Streamable HTTP (Claude.ai) | `POST /mcp` |
| SSE (Claude Desktop / Code) | `/mcp/sse` |

Remote MCP uses OAuth bearer tokens (see below). Tool results are JSON text: success payloads or `{ "error": "…" }`.

Restart the MCP HTTP process after tool changes so clients pick up new schemas.

### Generic DB tools (`crm` + `analytics` models)

`list_models` · `describe_model` (`model`) · `query_records` · `get_record` · `count_records`

`query_records` / `count_records`: `model`, optional `filters` (Django lookups, max depth 3), `search`, `order_by`, `limit` (cap **50**), `fields`.  
Lookups: `exact`, `iexact`, `contains`, `icontains`, `in`, `gt`, `gte`, `lt`, `lte`, `isnull`, `startswith`, `istartswith`, `endswith`, `iendswith`, `range`.  
`password` fields are redacted.

### Domain tools

| Tool | Required | Other args |
| --- | --- | --- |
| `search_contacts` | `query` | `limit` (default 20) |
| `get_contact` | `contact_id` | |
| `create_contact` | `first_name`, `last_name` | `email`, `phone`, `job_title`, `company_id`, `company_name`, `linkedin_url`, `status`, `headline`, `notes`, `source` (default `"mcp"`) |
| `update_contact` | `contact_id` | `job_title`, `company_name`, `headline`, `bio`, `notes`, `linkedin_url`, `status` |
| `search_companies` | `query` | `limit` |
| `get_company` | `company_id` | |
| `create_company` | `name` | `industry`, `website`, `phone`, `email`, `city`, `state`, `country`, `description`, `linkedin_url`, `employee_count`, `icp_fit_score`, `icp_fit_tier` (`A`–`D`) |
| `update_company` | `company_id` | `description`, `industry`, `website`, `employee_count`, `icp_fit_score`, `icp_fit_tier`, `notes` |
| `fetch_url` | `url` | `max_chars` (default 25000) |
| `create_signal` | `source_url`, `headline`, `summary` | `source_type`, `relevance` (`high`/`medium`/`low`), `potential_action`, `competitors`, `competitors_notes`, `mentioned_company_names[]` |
| `update_signal` | `signal_id` | `headline`, `summary`, `relevance`, `potential_action`, `status` (`logged`/`actioned`/`archived`), `competitors`, `competitors_notes` |
| `get_signals` | | `relevance`, `status`, `limit` |
| `get_pain_signals` | | `company_id`, `limit` |
| `create_pain_signal` | `description` | `company_id`, `contact_id`, `source` |
| `get_deals` | | `stage`, `company_id`, `contact_id`, `limit` |
| `create_deal` | `name`, `contact_id` | `company_id`, `amount` (default 0), `currency`, `stage`, `probability`, `priority`, `expected_close_date` (`YYYY-MM-DD`, default today+30d), `description`, `notes` |
| `get_activities` | | `contact_id`, `company_id`, `deal_id`, `limit` |
| `create_activity` | `activity_type`, `subject` | FKs, `body`, `status` (`pending`/`completed`), `direction` (`inbound`/`outbound`) |

Signal **model** statuses are `logged` | `follow_up` | `done`; MCP `update_signal` documents `logged` | `actioned` | `archived` — those enums can disagree with the DB.

### Create tools (detail)

Suggested order: `search_companies` / `create_company` → `create_contact` → `create_deal`. These tools do not set `owner`.

#### `create_company`

Fails if a company with the same name already exists (case-insensitive).

**Success**

```json
{ "created": true, "company": { "id": 1, "name": "Acme Corp", "is_active": true, "…" } }
```

**Errors:** `"name is required"` · `"Company already exists (id=…, name=…)"`

#### `create_contact`

Prefer `company_id` when the company already exists; otherwise `company_name` will get-or-create. Email is lowercased and must be unique if set. Default `status` is `lead`; default `source` is `mcp`.

**Success**

```json
{ "created": true, "contact": { "id": 1, "first_name": "Jane", "last_name": "Smith", "…" } }
```

**Errors:** `"first_name and last_name are required"` · `"Contact with this email already exists (id=…)"` · `"Company not found"`

#### `create_deal`

Requires an existing contact. Company defaults to the contact’s company unless `company_id` is set. Stages: `prospecting` | `qualification` | `proposal` | `negotiation` | `closed_won` | `closed_lost`. Priorities: `low` | `medium` | `high`.

**Success**

```json
{ "created": true, "deal": { "id": 1, "name": "Acme — annual", "amount": "25000", "…" } }
```

**Errors:** `"name is required"` · `"contact_id is required"` · `"Contact not found"` · `"Company not found"` · `"amount must be a number"` · `"expected_close_date must be YYYY-MM-DD"`

---

## MCP OAuth 2.1 (Claude.ai)

In-memory clients/codes/tokens (lost on restart). Access tokens last **30 days**.

| Method | Path | Role |
| --- | --- | --- |
| `GET` | `/.well-known/oauth-protected-resource` | RFC 9728 — `resource` = `{origin}/mcp` |
| `GET` | `/.well-known/oauth-authorization-server` | RFC 8414 — code + PKCE S256 |
| `POST` | `/oauth/register` | RFC 7591 — body `redirect_uris`; **201** `{client_id, client_secret, redirect_uris}` |
| `GET`/`POST` | `/oauth/authorize` | Django **login required**; POST issues code, redirects with `code` + `state` |
| `POST` | `/oauth/token` | form: `grant_type=authorization_code`, `code`, `client_id`, `code_verifier` → `{ access_token, token_type: "bearer", expires_in }` |

---

## Error Handling

Typical DRF status codes:

- `200 OK` / `201 Created`
- `400 Bad Request` — validation errors (field maps) or `{ "error": "…" }` on custom endpoints
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`
- `405 Method Not Allowed`

Validation example:

```json
{ "email": ["Enter a valid email address."] }
```

---

## Examples

### Obtain a token and list contacts

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"secret"}' | jq -r .token)

curl -s "http://localhost:8000/api/contacts/?search=jane" \
  -H "Authorization: Token $TOKEN"
```

### Create a company (REST)

```bash
curl -X POST http://localhost:8000/api/companies/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","industry":"Technology","website":"https://acme.example"}'
```

### Python (requests)

```python
import requests

base = "http://localhost:8000"
token = requests.post(
    f"{base}/api/token/",
    json={"username": "admin", "password": "secret"},
).json()["token"]
headers = {"Authorization": f"Token {token}"}

contacts = requests.get(f"{base}/api/contacts/", headers=headers, params={"search": "jane"}).json()
```

---

## Known gaps

- REST covers core CRM objects + analytics; signals, sequences, and most newsletter flows are HTML UI (plus MCP / public subscribe).
- Serializers omit many model columns.
- `DashboardTemplateViewSet` is currently public (`AllowAny`) for testing.
- Throttling is disabled; older docs mentioning rate limits are obsolete.
- Basic Authentication is **not** configured; use Token or Session auth.

---

*For the compact live-surface reference, see [`Kikodo CRM API spec.md`](./Kikodo%20CRM%20API%20spec.md).*
