# Kikodo CRM - API Documentation

## Overview
The Kikodo CRM provides a comprehensive REST API built with Django REST Framework. This API allows you to integrate the CRM with external systems, build custom applications, and automate CRM operations.

## Base URL
```
http://localhost:8000/crm/api/
```

## Authentication
The API supports multiple authentication methods:

### Session Authentication
- Use Django's built-in session authentication
- Include session cookies in requests
- Suitable for web applications

### Token Authentication
- Generate API tokens for programmatic access
- Include token in Authorization header: `Token <your-token>`
- Suitable for mobile apps and external integrations

### Basic Authentication
- Username/password authentication
- Include credentials in Authorization header
- Use with HTTPS only

## Response Format
All API responses are in JSON format:

```json
{
    "count": 25,
    "next": "http://localhost:8000/crm/api/contacts/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1234567890",
            "job_title": "Sales Manager",
            "company": 1,
            "status": "active",
            "created_at": "2025-09-28T10:00:00Z",
            "updated_at": "2025-09-28T10:00:00Z"
        }
    ]
}
```

## Pagination
All list endpoints support pagination:
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

Example:
```
GET /crm/api/contacts/?page=2&page_size=10
```

## Filtering
Most endpoints support filtering by various fields:

### Contacts API
```
GET /crm/api/contacts/?status=active
GET /crm/api/contacts/?company=1
GET /crm/api/contacts/?first_name__icontains=john
```

### Companies API
```
GET /crm/api/companies/?industry=technology
GET /crm/api/companies/?annual_revenue__gte=1000000
```

### Deals API
```
GET /crm/api/deals/?stage=proposal
GET /crm/api/deals/?amount__gte=50000
GET /crm/api/deals/?expected_close_date__gte=2025-01-01
```

### Activities API
```
GET /crm/api/activities/?activity_type=call
GET /crm/api/activities/?status=pending
GET /crm/api/activities/?due_date__gte=2025-01-01
```

## Sorting
Add `ordering` parameter to sort results:
```
GET /crm/api/contacts/?ordering=last_name
GET /crm/api/deals/?ordering=-amount
GET /crm/api/activities/?ordering=due_date
```

## Endpoints

### Contacts

#### List Contacts
```http
GET /crm/api/contacts/
```

**Query Parameters:**
- `status`: Filter by status (active, inactive, lead, customer)
- `company`: Filter by company ID
- `first_name__icontains`: Search in first name
- `last_name__icontains`: Search in last name
- `email__icontains`: Search in email
- `ordering`: Sort by field (prefix with `-` for descending)

**Response:**
```json
{
    "count": 8,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1234567890",
            "job_title": "Sales Manager",
            "department": "Sales",
            "company": 1,
            "company_name": "Acme Corp",
            "status": "active",
            "is_active": true,
            "created_at": "2025-09-28T10:00:00Z",
            "updated_at": "2025-09-28T10:00:00Z"
        }
    ]
}
```

#### Create Contact
```http
POST /crm/api/contacts/
```

**Request Body:**
```json
{
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane.smith@example.com",
    "phone": "+1234567891",
    "job_title": "Marketing Director",
    "department": "Marketing",
    "company": 2,
    "status": "active"
}
```

#### Get Contact
```http
GET /crm/api/contacts/{id}/
```

#### Update Contact
```http
PUT /crm/api/contacts/{id}/
PATCH /crm/api/contacts/{id}/
```

#### Delete Contact
```http
DELETE /crm/api/contacts/{id}/
```

### Companies

#### List Companies
```http
GET /crm/api/companies/
```

**Query Parameters:**
- `industry`: Filter by industry
- `annual_revenue__gte`: Minimum annual revenue
- `annual_revenue__lte`: Maximum annual revenue
- `employee_count__gte`: Minimum employee count
- `city`: Filter by city
- `state`: Filter by state
- `name__icontains`: Search in company name

**Response:**
```json
{
    "count": 5,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Acme Corp",
            "website": "https://acme.com",
            "description": "Leading technology company",
            "industry": "Technology",
            "annual_revenue": 5000000,
            "employee_count": 50,
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "country": "USA",
            "status": "active",
            "is_active": true,
            "created_at": "2025-09-28T10:00:00Z",
            "updated_at": "2025-09-28T10:00:00Z"
        }
    ]
}
```

#### Create Company
```http
POST /crm/api/companies/
```

**Request Body:**
```json
{
    "name": "TechStart Inc",
    "website": "https://techstart.com",
    "description": "Innovative startup company",
    "industry": "Technology",
    "annual_revenue": 1000000,
    "employee_count": 25,
    "address": "456 Innovation Ave",
    "city": "Austin",
    "state": "TX",
    "country": "USA",
    "status": "active"
}
```

#### Get Company
```http
GET /crm/api/companies/{id}/
```

#### Update Company
```http
PUT /crm/api/companies/{id}/
PATCH /crm/api/companies/{id}/
```

#### Delete Company
```http
DELETE /crm/api/companies/{id}/
```

### Deals

#### List Deals
```http
GET /crm/api/deals/
```

**Query Parameters:**
- `stage`: Filter by pipeline stage
- `amount__gte`: Minimum deal amount
- `amount__lte`: Maximum deal amount
- `expected_close_date__gte`: Deals closing after date
- `expected_close_date__lte`: Deals closing before date
- `contact`: Filter by contact ID
- `company`: Filter by company ID

**Response:**
```json
{
    "count": 8,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Enterprise Software License",
            "description": "Annual software license for enterprise",
            "amount": 50000,
            "stage": "proposal",
            "probability": 75,
            "expected_close_date": "2025-12-31",
            "actual_close_date": null,
            "contact": 1,
            "contact_name": "John Doe",
            "company": 1,
            "company_name": "Acme Corp",
            "is_active": true,
            "created_at": "2025-09-28T10:00:00Z",
            "updated_at": "2025-09-28T10:00:00Z"
        }
    ]
}
```

#### Create Deal
```http
POST /crm/api/deals/
```

**Request Body:**
```json
{
    "name": "Q4 Software License",
    "description": "Quarterly software license renewal",
    "amount": 25000,
    "stage": "negotiation",
    "probability": 60,
    "expected_close_date": "2025-12-15",
    "contact": 1,
    "company": 1
}
```

#### Get Deal
```http
GET /crm/api/deals/{id}/
```

#### Update Deal
```http
PUT /crm/api/deals/{id}/
PATCH /crm/api/deals/{id}/
```

#### Delete Deal
```http
DELETE /crm/api/deals/{id}/
```

### Activities

#### List Activities
```http
GET /crm/api/activities/
```

**Query Parameters:**
- `activity_type`: Filter by type (call, email, meeting, task, note)
- `status`: Filter by status (pending, in_progress, completed, cancelled)
- `due_date__gte`: Activities due after date
- `due_date__lte`: Activities due before date
- `contact`: Filter by contact ID
- `company`: Filter by company ID
- `deal`: Filter by deal ID

**Response:**
```json
{
    "count": 20,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "subject": "Follow-up call with John Doe",
            "description": "Discuss proposal details and next steps",
            "activity_type": "call",
            "status": "pending",
            "priority": "high",
            "due_date": "2025-09-30T14:00:00Z",
            "completed_date": null,
            "contact": 1,
            "contact_name": "John Doe",
            "company": 1,
            "company_name": "Acme Corp",
            "deal": 1,
            "deal_name": "Enterprise Software License",
            "created_at": "2025-09-28T10:00:00Z",
            "updated_at": "2025-09-28T10:00:00Z"
        }
    ]
}
```

#### Create Activity
```http
POST /crm/api/activities/
```

**Request Body:**
```json
{
    "subject": "Product demo meeting",
    "description": "Demonstrate new features to potential client",
    "activity_type": "meeting",
    "status": "pending",
    "priority": "high",
    "due_date": "2025-10-05T10:00:00Z",
    "contact": 1,
    "company": 1,
    "deal": 1
}
```

#### Get Activity
```http
GET /crm/api/activities/{id}/
```

#### Update Activity
```http
PUT /crm/api/activities/{id}/
PATCH /crm/api/activities/{id}/
```

#### Delete Activity
```http
DELETE /crm/api/activities/{id}/
```

### Tags

#### List Tags
```http
GET /crm/api/tags/
```

#### Create Tag
```http
POST /crm/api/tags/
```

**Request Body:**
```json
{
    "name": "VIP Customer",
    "color": "#FF6B6B",
    "description": "High-value customers"
}
```

### Pipelines

#### List Pipelines
```http
GET /crm/api/pipelines/
```

#### Create Pipeline
```http
POST /crm/api/pipelines/
```

**Request Body:**
```json
{
    "name": "Sales Pipeline",
    "description": "Standard sales process",
    "is_active": true
}
```

### Pipeline Stages

#### List Pipeline Stages
```http
GET /crm/api/pipeline-stages/
```

#### Create Pipeline Stage
```http
POST /crm/api/pipeline-stages/
```

**Request Body:**
```json
{
    "name": "Qualification",
    "description": "Initial qualification stage",
    "pipeline": 1,
    "order": 1,
    "is_active": true
}
```

## Error Handling

### HTTP Status Codes
- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `405 Method Not Allowed`: HTTP method not supported
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
    "error": "Validation failed",
    "details": {
        "email": ["This field is required."],
        "phone": ["Enter a valid phone number."]
    }
}
```

## Rate Limiting
- **Default Limit**: 1000 requests per hour per user
- **Burst Limit**: 100 requests per minute
- **Headers**: Rate limit information included in response headers

## Examples

### Python Example
```python
import requests

# Set up authentication
session = requests.Session()
session.auth = ('admin', 'admin123')

# Get all contacts
response = session.get('http://localhost:8000/crm/api/contacts/')
contacts = response.json()

# Create a new contact
new_contact = {
    'first_name': 'Alice',
    'last_name': 'Johnson',
    'email': 'alice.johnson@example.com',
    'phone': '+1234567892',
    'job_title': 'Product Manager',
    'status': 'active'
}
response = session.post('http://localhost:8000/crm/api/contacts/', json=new_contact)
```

### JavaScript Example
```javascript
// Using fetch API
const apiUrl = 'http://localhost:8000/crm/api/';

// Get all deals
fetch(`${apiUrl}deals/`, {
    headers: {
        'Authorization': 'Token your-token-here',
        'Content-Type': 'application/json'
    }
})
.then(response => response.json())
.then(data => console.log(data));

// Create a new activity
const newActivity = {
    subject: 'Follow-up email',
    description: 'Send proposal details',
    activity_type: 'email',
    status: 'pending',
    priority: 'medium',
    due_date: '2025-10-01T09:00:00Z'
};

fetch(`${apiUrl}activities/`, {
    method: 'POST',
    headers: {
        'Authorization': 'Token your-token-here',
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(newActivity)
})
.then(response => response.json())
.then(data => console.log(data));
```

### cURL Examples
```bash
# Get all contacts
curl -X GET "http://localhost:8000/crm/api/contacts/" \
     -H "Authorization: Token your-token-here"

# Create a new company
curl -X POST "http://localhost:8000/crm/api/companies/" \
     -H "Authorization: Token your-token-here" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "New Company Inc",
       "website": "https://newcompany.com",
       "industry": "Technology",
       "annual_revenue": 2000000,
       "employee_count": 30,
       "status": "active"
     }'

# Update a deal
curl -X PATCH "http://localhost:8000/crm/api/deals/1/" \
     -H "Authorization: Token your-token-here" \
     -H "Content-Type: application/json" \
     -d '{
       "stage": "closed_won",
       "actual_close_date": "2025-09-28"
     }'
```

## Webhooks (Coming Soon)
- Real-time notifications for data changes
- Configurable webhook endpoints
- Event filtering and payload customization

## SDKs (Coming Soon)
- Python SDK
- JavaScript/Node.js SDK
- PHP SDK
- Ruby SDK

---

*For the latest API documentation and updates, check the project repository.*
