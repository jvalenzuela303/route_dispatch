# API Endpoints Reference - Claude Logistics

## Índice

- [Authentication](#authentication)
- [Orders](#orders)
- [Invoices](#invoices)
- [Routes](#routes)
- [Reports](#reports)

---

## Authentication

### POST /api/auth/login
Autenticar usuario y obtener JWT token.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "username": "admin",
    "email": "admin@botilleria.cl",
    "role": "Administrador"
  }
}
```

---

## Orders

### POST /api/orders
Crear nuevo pedido con workflow completo.

**Permisos:** Admin, Encargado, Vendedor

**Request:**
```json
{
  "customer_name": "Juan Pérez",
  "customer_phone": "+56912345678",
  "customer_email": "juan@example.cl",
  "address_text": "Av. Brasil 1234, Rancagua",
  "source_channel": "WEB",
  "notes": "Entregar en portería"
}
```

**Response (201):**
```json
{
  "order": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "order_number": "ORD-20260122-0001",
    "customer_name": "Juan Pérez",
    "customer_phone": "+56912345678",
    "customer_email": "juan@example.cl",
    "address_text": "Av. Brasil 1234, Rancagua",
    "order_status": "PENDIENTE",
    "source_channel": "WEB",
    "delivery_date": "2026-01-23",
    "geocoding_confidence": "HIGH",
    "created_at": "2026-01-22T10:30:00-03:00",
    "updated_at": "2026-01-22T10:30:00-03:00",
    "created_by": {
      "id": "user-uuid",
      "username": "admin",
      "email": "admin@botilleria.cl"
    }
  },
  "warnings": [],
  "next_steps": [
    "Crear factura/boleta para transicionar pedido a DOCUMENTADO",
    "Una vez documentado, el pedido estará listo para ser incluido en una ruta"
  ],
  "delivery_date_info": {
    "delivery_date": "2026-01-23",
    "was_overridden": false
  },
  "workflow_status": "ORDER_CREATED"
}
```

---

### GET /api/orders
Listar pedidos con filtros.

**Permisos:** Todos (RBAC aplicado)

**Query Parameters:**
- `skip` (int): Offset para paginación (default: 0)
- `limit` (int): Máximo resultados (default: 100, max: 1000)
- `status` (OrderStatus): Filtrar por estado
- `delivery_date` (date): Filtrar por fecha de entrega
- `search` (str): Buscar en order_number, customer_name, customer_phone

**Example:**
```
GET /api/orders?status=DOCUMENTADO&delivery_date=2026-01-23&limit=50
```

**Response (200):**
```json
[
  {
    "id": "uuid",
    "order_number": "ORD-20260122-0001",
    "customer_name": "Juan Pérez",
    "order_status": "DOCUMENTADO",
    "delivery_date": "2026-01-23",
    ...
  },
  ...
]
```

---

### PUT /api/orders/{order_id}/status
Transicionar pedido a nuevo estado.

**Permisos:** Depende del estado

**Request:**
```json
{
  "new_status": "EN_RUTA",
  "route_id": "route-uuid"
}
```

**Response (200):**
```json
{
  "id": "order-uuid",
  "order_number": "ORD-20260122-0001",
  "order_status": "EN_RUTA",
  "assigned_route": {
    "id": "route-uuid",
    "route_name": "RUTA-20260123-001"
  },
  ...
}
```

---

## Invoices

### POST /api/invoices
Crear factura y auto-transicionar pedido a DOCUMENTADO.

**Permisos:** Admin, Encargado, Vendedor

**Request:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "invoice_number": "FAC-001",
  "invoice_type": "FACTURA",
  "total_amount": 50000
}
```

**Response (201):**
```json
{
  "invoice": {
    "id": "invoice-uuid",
    "invoice_number": "FAC-001",
    "invoice_type": "FACTURA",
    "total_amount": 50000,
    "issued_at": "2026-01-22T11:00:00-03:00",
    "created_at": "2026-01-22T11:00:00-03:00",
    "order": {
      "id": "order-uuid",
      "order_number": "ORD-20260122-0001",
      "customer_name": "Juan Pérez"
    },
    "created_by": {
      "id": "user-uuid",
      "username": "admin"
    }
  },
  "order_id": "order-uuid",
  "order_status": "DOCUMENTADO",
  "transition": {
    "from_status": "EN_PREPARACION",
    "to_status": "DOCUMENTADO",
    "triggered_by": "invoice_creation",
    "business_rule": "BR-005: Auto-transition on invoice linking",
    "timestamp": "2026-01-22T11:00:00-03:00"
  },
  "next_steps": [
    "Pedido ORD-20260122-0001 ahora está DOCUMENTADO",
    "Delivery date: 2026-01-23",
    "El pedido puede ser incluido en una ruta de entrega"
  ],
  "workflow_status": "ORDER_DOCUMENTED"
}
```

---

## Routes

### POST /api/routes/generate
Generar ruta optimizada para fecha de entrega.

**Permisos:** Admin, Encargado

**Request:**
```json
{
  "delivery_date": "2026-01-23"
}
```

**Response (201):**
```json
{
  "route": {
    "id": "route-uuid",
    "route_name": "RUTA-20260123-001",
    "route_date": "2026-01-23",
    "status": "DRAFT",
    "total_distance_km": 15.3,
    "estimated_duration_minutes": 45,
    "created_at": "2026-01-22T12:00:00-03:00",
    "created_by": {
      "id": "user-uuid",
      "username": "admin"
    },
    "stops_count": 8
  },
  "stop_count": 8,
  "status": "DRAFT",
  "next_steps": [
    "Revise la ruta generada (8 paradas, 15.3 km)",
    "Active la ruta para asignar al repartidor y notificar clientes",
    "Use POST /api/routes/route-uuid/activate para activar"
  ]
}
```

---

### POST /api/routes/{route_id}/activate
Activar ruta y asignar a repartidor.

**Permisos:** Admin, Encargado

**Request:**
```json
{
  "driver_id": "driver-uuid"
}
```

**Response (200):**
```json
{
  "route": {
    "id": "route-uuid",
    "route_name": "RUTA-20260123-001",
    "status": "ACTIVE",
    "assigned_driver": {
      "id": "driver-uuid",
      "username": "repartidor1",
      "email": "repartidor1@botilleria.cl"
    },
    "stops": [
      {
        "id": "stop-uuid",
        "stop_sequence": 1,
        "order": {
          "id": "order-uuid",
          "order_number": "ORD-20260122-0001",
          "customer_name": "Juan Pérez",
          "address_text": "Av. Brasil 1234"
        },
        "latitude": -34.1706,
        "longitude": -70.7407,
        "delivered": false
      },
      ...
    ]
  },
  "orders_count": 8,
  "notifications_sent": 8,
  "driver": {
    "id": "driver-uuid",
    "username": "repartidor1",
    "email": "repartidor1@botilleria.cl"
  },
  "status": "ACTIVE",
  "next_steps": [
    "Ruta RUTA-20260123-001 ACTIVADA",
    "8 pedidos en ruta EN_RUTA",
    "8 notificaciones enviadas a clientes",
    "Repartidor puede comenzar entregas"
  ],
  "workflow_status": "ROUTE_ACTIVATED"
}
```

---

### GET /api/routes/{route_id}/map-data
Obtener datos para visualización en mapa.

**Permisos:** Todos (RBAC)

**Response (200):**
```json
{
  "route_id": "route-uuid",
  "route_name": "RUTA-20260123-001",
  "route_date": "2026-01-23",
  "depot_latitude": -34.1706,
  "depot_longitude": -70.7407,
  "stops": [
    {
      "stop_sequence": 1,
      "latitude": -34.1750,
      "longitude": -70.7450,
      "customer_name": "Juan Pérez",
      "address": "Av. Brasil 1234, Rancagua",
      "order_number": "ORD-20260122-0001"
    },
    {
      "stop_sequence": 2,
      "latitude": -34.1800,
      "longitude": -70.7500,
      "customer_name": "María López",
      "address": "Calle O'Higgins 567, Rancagua",
      "order_number": "ORD-20260122-0002"
    },
    ...
  ],
  "total_distance_km": 15.3,
  "estimated_duration_minutes": 45
}
```

---

## Reports

### GET /api/reports/compliance
Reporte de compliance para rango de fechas.

**Permisos:** Admin, Encargado

**Query Parameters:**
- `start_date` (date, required): Inicio del período
- `end_date` (date, required): Fin del período (máx 90 días)

**Example:**
```
GET /api/reports/compliance?start_date=2026-01-15&end_date=2026-01-22
```

**Response (200):**
```json
{
  "period_start": "2026-01-15",
  "period_end": "2026-01-22",
  "orders": {
    "total": 150,
    "delivered": 142,
    "in_progress": 5,
    "pending": 3,
    "with_incidence": 2
  },
  "compliance": {
    "cutoff_compliance": 0.98,
    "invoice_compliance": 1.0,
    "geocoding_quality": 0.95
  },
  "notifications": {
    "sent": 145,
    "failed": 3,
    "pending": 0,
    "delivery_rate": 0.98
  },
  "generated_at": "2026-01-22T14:30:00-03:00"
}
```

---

### GET /api/reports/daily-operations
Reporte de operaciones diarias.

**Permisos:** Admin, Encargado

**Query Parameters:**
- `report_date` (date): Fecha del reporte (default: hoy)

**Response (200):**
```json
{
  "report_date": "2026-01-22",
  "orders_created_today": 25,
  "orders_by_status": {
    "pendiente": 10,
    "en_preparacion": 15,
    "documentado": 20,
    "en_ruta": 8,
    "entregado": 142,
    "incidencia": 2
  },
  "routes": {
    "total_routes": 50,
    "active_routes": 3,
    "completed_routes": 45,
    "draft_routes": 2
  },
  "deliveries_completed_today": 35,
  "pending_invoices": 15,
  "orders_ready_for_routing": 20,
  "generated_at": "2026-01-22T14:30:00-03:00"
}
```

---

### GET /api/reports/summary
Resumen ejecutivo completo.

**Permisos:** Admin, Encargado

**Response (200):**
```json
{
  "generated_at": "2026-01-22T14:30:00-03:00",
  "daily_operations": { ... },
  "compliance_7_days": { ... },
  "compliance_30_days": { ... },
  "summary": {
    "orders_today": 25,
    "active_routes": 3,
    "pending_invoices": 15,
    "compliance_score_7d": 0.976,
    "notification_rate_7d": 0.98
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "INVALID_STATE_TRANSITION",
  "message": "Cannot transition from PENDIENTE to ENTREGADO",
  "details": {
    "from_status": "PENDIENTE",
    "to_status": "ENTREGADO"
  },
  "path": "/api/orders/uuid/status"
}
```

### 401 Unauthorized
```json
{
  "error": "TOKEN_EXPIRED",
  "message": "Token has expired",
  "details": {},
  "path": "/api/orders"
}
```

### 403 Forbidden
```json
{
  "error": "INSUFFICIENT_PERMISSIONS",
  "message": "Role 'Vendedor' cannot execute 'delete_order'",
  "details": {
    "action": "delete_order",
    "user_role": "Vendedor",
    "required_role": "Administrador"
  },
  "path": "/api/orders/uuid"
}
```

### 404 Not Found
```json
{
  "error": "ORDER_NOT_FOUND",
  "message": "Order uuid not found",
  "details": {},
  "path": "/api/orders/uuid"
}
```

### 422 Validation Error
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "errors": [
      {
        "field": "customer_phone",
        "message": "Phone must be Chilean format (+56XXXXXXXXX)",
        "type": "value_error"
      }
    ]
  },
  "path": "/api/orders"
}
```

---

## Rate Limiting

**Not implemented yet** - Recommended for production:
- 100 requests/minute per IP
- 1000 requests/hour per user

---

## Versioning

Current version: **v1.0**
All endpoints prefixed with `/api/`

Future versions will use: `/api/v2/`

---

**Last updated:** 2026-01-22
**API Documentation:** http://localhost:8000/docs
