# Konozy AI - API Contracts for Dashboard

This document describes the API endpoints available for the Next.js dashboard.

## Base URL
```
http://localhost:8000
```

---

## 1. Trigger Order Sync

**Endpoint:** `POST /api/v1/orders/sync`

**Description:** Triggers Amazon order synchronization. Returns execution_id for tracking.

**Request:**
```json
{
  "start_date": "2025-01-01T00:00:00Z",  // Optional: ISO 8601 date
  "end_date": "2025-01-31T23:59:59Z",    // Optional: ISO 8601 date
  "marketplace": "amazon"                 // Optional: default "amazon"
}
```

**Response (200 OK):**
```json
{
  "status": "started",
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Order sync started successfully",
  "marketplace": "amazon",
  "start_date": "2025-01-01T00:00:00Z",
  "end_date": "2025-01-31T23:59:59Z",
  "summary": {
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "total_orders": 10,
    "created_invoices": 8,
    "invoices_failed": 2,
    "failed_items": [...],
    "successful": 8
  }
}
```

**Example cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/orders/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-01-31T23:59:59Z"
  }'
```

---

## 2. Get Execution Summary

**Endpoint:** `GET /api/v1/executions/{execution_id}`

**Description:** Returns high-level summary of a sync execution.

**Path Parameters:**
- `execution_id` (UUID): Execution ID returned from sync endpoint

**Response (200 OK):**
```json
{
  "execution_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",  // "running" | "completed" | "completed_with_errors"
  "marketplace": "amazon",
  "total_orders": 10,
  "successful": 8,
  "failed": 2,
  "invoices_created": 8,
  "invoices_failed": 2,
  "started_at": "2025-01-15T10:30:00+00:00",
  "completed_at": "2025-01-15T10:35:00+00:00",
  "start_date": "2025-01-01T00:00:00Z",
  "end_date": "2025-01-31T23:59:59Z"
}
```

**Example cURL:**
```bash
curl "http://localhost:8000/api/v1/executions/550e8400-e29b-41d4-a716-446655440000"
```

**Error Responses:**
- `400 Bad Request`: Invalid execution_id format
- `404 Not Found`: Execution not found

---

## 3. Get Execution Events

**Endpoint:** `GET /api/v1/executions/{execution_id}/events`

**Description:** Returns detailed event list for an execution, ordered by timestamp.

**Path Parameters:**
- `execution_id` (UUID): Execution ID

**Response (200 OK):**
```json
[
  {
    "timestamp": "2025-01-15T10:30:00+00:00",
    "event_type": "sync_started",
    "aggregate_id": "sync-550e8400-e29b-41d4-a716-446655440000",
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "marketplace": "amazon",
      "start_date": "2025-01-01T00:00:00Z",
      "end_date": "2025-01-31T23:59:59Z"
    }
  },
  {
    "timestamp": "2025-01-15T10:30:05+00:00",
    "event_type": "order_fetched",
    "aggregate_id": "112-3456789-0123456",
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "order_id": "112-3456789-0123456",
      "marketplace": "amazon",
      "buyer_email": "buyer@example.com",
      "purchase_date": "2025-01-15T10:30:00Z"
    }
  },
  {
    "timestamp": "2025-01-15T10:30:10+00:00",
    "event_type": "invoice_created",
    "aggregate_id": "112-3456789-0123456",
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "order_id": "112-3456789-0123456",
      "invoice_id": 12345,
      "partner_id": 67890,
      "invoice_lines_count": 2
    }
  },
  {
    "timestamp": "2025-01-15T10:35:00+00:00",
    "event_type": "sync_completed",
    "aggregate_id": "sync-550e8400-e29b-41d4-a716-446655440000",
    "execution_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "marketplace": "amazon",
      "total_orders": 10,
      "successful": 8,
      "failed": 2,
      "invoices_created": 8,
      "invoices_failed": 2
    }
  }
]
```

**Event Types:**
- `sync_started`: Sync run started
- `order_fetched`: Order fetched from Amazon
- `invoice_created`: Invoice created in Odoo
- `invoice_failed`: Invoice creation failed
- `sync_completed`: Sync run completed

**Example cURL:**
```bash
curl "http://localhost:8000/api/v1/executions/550e8400-e29b-41d4-a716-446655440000/events"
```

---

## 4. List Orders

**Endpoint:** `GET /api/v1/orders`

**Description:** List latest orders with pagination.

**Query Parameters:**
- `limit` (int, optional): Number of orders to return (default: 50)
- `offset` (int, optional): Number of orders to skip (default: 0)

**Response (200 OK):**
```json
{
  "orders": [
    {
      "order_id": "112-3456789-0123456",
      "marketplace": "amazon",
      "buyer_email": "buyer@example.com",
      "purchase_date": "2025-01-15T10:30:00Z",
      "order_status": "Shipped",
      "total": {
        "amount": "125.50",
        "currency": "USD"
      },
      "items": [...]
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

**Example cURL:**
```bash
curl "http://localhost:8000/api/v1/orders?limit=10&offset=0"
```

---

## Dashboard Integration Flow

### 1. Trigger Sync
```javascript
const response = await fetch('/api/v1/orders/sync', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    start_date: '2025-01-01T00:00:00Z',
    end_date: '2025-01-31T23:59:59Z'
  })
});
const { execution_id } = await response.json();
```

### 2. Poll Execution Status
```javascript
const pollStatus = async (executionId) => {
  const response = await fetch(`/api/v1/executions/${executionId}`);
  const status = await response.json();
  
  if (status.status === 'running') {
    // Still running, poll again
    setTimeout(() => pollStatus(executionId), 2000);
  } else {
    // Completed, show summary
    displaySummary(status);
  }
};
```

### 3. Show Events Timeline
```javascript
const response = await fetch(`/api/v1/executions/${executionId}/events`);
const events = await response.json();

// Render events in timeline component
events.forEach(event => {
  renderEvent(event);
});
```

---

## Error Handling

All endpoints return standard HTTP status codes:
- `200 OK`: Success
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error response format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Notes

- All timestamps are in ISO 8601 format with timezone
- Execution IDs are UUIDs (v4)
- Events are ordered by timestamp (ascending)
- Status values: `running`, `completed`, `completed_with_errors`
- Marketplace currently supports: `amazon`
