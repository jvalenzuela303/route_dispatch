# Database Schema Documentation

## Overview

This document describes the database schema for the **Route Dispatch System** (Claude Logistics), a comprehensive logistics management platform for a beverage distribution company in Rancagua, Chile.

The schema is designed to support:
- Order lifecycle management from creation to delivery
- Geographic routing with PostGIS spatial data
- Role-based access control (RBAC)
- Fiscal document tracking (Chilean invoices/receipts)
- Comprehensive audit trail
- Route optimization with stop sequencing

**Database:** PostgreSQL 15+ with PostGIS extension
**ORM:** SQLAlchemy 2.0+
**Migration Tool:** Alembic

---

## Database Diagram

See `/home/juan/Desarrollo/route_dispatch/docs/erd.png` for the Entity Relationship Diagram.

---

## Tables

### 1. `roles`

Defines user roles and their permissions in the system.

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `role_name` | VARCHAR(100) | NOT NULL, UNIQUE | Role name (e.g., "Administrador") |
| `description` | TEXT | NULLABLE | Role description |
| `permissions` | JSONB | NOT NULL | Flexible permissions structure |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Relationships:**
- One-to-Many with `users` (one role can have many users)

**Business Roles:**
- **Administrador**: Full system access + override capabilities
- **Encargado de Bodega**: Generate routes, approve deliveries
- **Vendedor**: Create orders and invoices
- **Repartidor**: View routes, update delivery status

**Indexes:**
- Primary key on `id`
- Unique index on `role_name`

**Sample Permissions Structure:**
```json
{
  "can_create_users": true,
  "can_manage_roles": true,
  "can_override_cutoff": true,
  "can_force_delivery_date": true,
  "can_delete_orders": false,
  "can_view_audit_logs": true,
  "can_manage_routes": true,
  "can_create_orders": true,
  "can_create_invoices": true
}
```

---

### 2. `users`

System users with authentication credentials and role assignment.

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `username` | VARCHAR(100) | NOT NULL, UNIQUE | Login username |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Email address (also used for login) |
| `password_hash` | VARCHAR(255) | NOT NULL | BCrypt/Argon2 hashed password |
| `role_id` | UUID | NOT NULL, FK → roles.id | Foreign key to roles |
| `active_status` | BOOLEAN | NOT NULL, DEFAULT TRUE | Account active status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Relationships:**
- Many-to-One with `roles` (many users can have one role)
- One-to-Many with `orders` (via `created_by_user_id`)
- One-to-Many with `routes` (via `assigned_driver_id`)
- One-to-Many with `invoices` (via `created_by_user_id`)
- One-to-Many with `audit_logs`

**Constraints:**
- `UNIQUE(username)`
- `UNIQUE(email)`
- `FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE RESTRICT`

**Indexes:**
- Primary key on `id`
- Index on `email`
- Index on `username`
- Index on `role_id`

---

### 3. `orders`

Customer orders tracking the complete delivery lifecycle.

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `order_number` | VARCHAR(50) | NOT NULL, UNIQUE | Format: ORD-YYYYMMDD-NNNN |
| `customer_name` | VARCHAR(255) | NOT NULL | Customer full name |
| `customer_phone` | VARCHAR(50) | NOT NULL | Contact phone number |
| `customer_email` | VARCHAR(255) | NULLABLE | Email for notifications |
| `address_text` | TEXT | NOT NULL | Original address as text |
| `address_coordinates` | GEOGRAPHY(POINT, 4326) | NULLABLE | PostGIS point (lat, lon) |
| `geocoding_confidence` | ENUM | NULLABLE | HIGH, MEDIUM, LOW, INVALID |
| `order_status` | ENUM | NOT NULL | Current order status |
| `source_channel` | ENUM | NOT NULL | WEB, RRSS, PRESENCIAL |
| `delivery_date` | DATE | NULLABLE | Assigned delivery date |
| `created_by_user_id` | UUID | NOT NULL, FK → users.id | Creator user |
| `assigned_route_id` | UUID | NULLABLE, FK → routes.id | Assigned route (if any) |
| `notes` | TEXT | NULLABLE | Additional notes |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Relationships:**
- Many-to-One with `users` (created_by)
- One-to-One with `invoices`
- Many-to-One with `routes` (assigned_route)

**Order Status Enum:**
1. `PENDIENTE` - Order just created
2. `EN_PREPARACION` - Being prepared in warehouse
3. `DOCUMENTADO` - Invoice linked (CRITICAL: enables routing)
4. `EN_RUTA` - Assigned to vehicle and in transit
5. `ENTREGADO` - Delivery confirmed
6. `INCIDENCIA` - Delivery failed

**Source Channel Enum:**
- `WEB` - Online web platform
- `RRSS` - Social media (WhatsApp, Instagram, Facebook)
- `PRESENCIAL` - In-person at physical location

**Geocoding Confidence Enum:**
- `HIGH` - Precise coordinates (exact address match)
- `MEDIUM` - Good coordinates (street-level accuracy)
- `LOW` - Approximate coordinates (neighborhood level)
- `INVALID` - Could not geocode (requires manual intervention)

**Constraints:**
- `UNIQUE(order_number)`
- `FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT`
- `FOREIGN KEY(assigned_route_id) REFERENCES routes(id) ON DELETE SET NULL`

**Indexes:**
- Primary key on `id`
- Index on `order_number`
- Index on `order_status`
- Index on `delivery_date`
- Index on `created_by_user_id`
- Index on `assigned_route_id`
- **GIST spatial index on `address_coordinates`** (enables efficient distance queries)

**Business Rules:**
- Cannot transition to `EN_RUTA` without `invoice_id`
- Auto-transitions to `DOCUMENTADO` when invoice is linked
- `delivery_date` determined by cut-off time rules:
  - Orders ≤ 12:00 PM → eligible for same-day delivery
  - Orders > 3:00 PM → next-day delivery
  - Admin can override with audit log

---

### 4. `invoices`

Fiscal documents (Chilean facturas/boletas) linked one-to-one with orders.

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `invoice_number` | VARCHAR(100) | NOT NULL, UNIQUE | Fiscal document number |
| `order_id` | UUID | NOT NULL, UNIQUE, FK → orders.id | One-to-one with order |
| `invoice_type` | ENUM | NOT NULL | FACTURA or BOLETA |
| `total_amount` | NUMERIC(10, 2) | NOT NULL, CHECK > 0 | Amount in Chilean pesos |
| `issued_at` | TIMESTAMPTZ | NOT NULL | Issue timestamp |
| `created_by_user_id` | UUID | NOT NULL, FK → users.id | Creator user |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Relationships:**
- One-to-One with `orders`
- Many-to-One with `users` (created_by)

**Invoice Type Enum:**
- `FACTURA` - Tax invoice (for businesses with RUT)
- `BOLETA` - Receipt (for individual customers)

**Constraints:**
- `UNIQUE(invoice_number)`
- `UNIQUE(order_id)` (enforces one-to-one)
- `CHECK(total_amount > 0)`
- `FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE`
- `FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT`

**Indexes:**
- Primary key on `id`
- Index on `invoice_number`
- Index on `order_id`

**Business Rules:**
- CRITICAL: An invoice must be linked before an order can be routed
- Linking an invoice triggers order state transition to `DOCUMENTADO`
- Deleting an order cascades to delete its invoice

---

### 5. `routes`

Delivery routes with optimized stop sequences.

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `route_name` | VARCHAR(255) | NOT NULL | Human-readable name |
| `route_date` | DATE | NOT NULL | Execution date |
| `assigned_driver_id` | UUID | NULLABLE, FK → users.id | Assigned driver |
| `status` | ENUM | NOT NULL | DRAFT, ACTIVE, COMPLETED |
| `started_at` | TIMESTAMPTZ | NULLABLE | When route started |
| `completed_at` | TIMESTAMPTZ | NULLABLE | When route completed |
| `total_distance_km` | NUMERIC(8, 2) | NULLABLE | Total distance in km |
| `estimated_duration_minutes` | INTEGER | NULLABLE | Estimated duration |
| `actual_duration_minutes` | INTEGER | NULLABLE | Actual duration (for ML) |
| `stop_sequence` | JSONB | NULLABLE | Array of order UUIDs |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Relationships:**
- Many-to-One with `users` (assigned_driver)
- One-to-Many with `orders`

**Route Status Enum:**
- `DRAFT` - Being planned, not yet assigned
- `ACTIVE` - Assigned to driver and in progress
- `COMPLETED` - All deliveries finished

**Stop Sequence Format:**
```json
["uuid-1", "uuid-2", "uuid-3", ...]
```
This array represents the optimized order of deliveries.

**Constraints:**
- `FOREIGN KEY(assigned_driver_id) REFERENCES users(id) ON DELETE SET NULL`

**Indexes:**
- Primary key on `id`
- Index on `route_date`
- Index on `status`
- Index on `assigned_driver_id`

**Business Rules:**
- Only orders in `DOCUMENTADO` status can be added to routes
- Transitioning to `ACTIVE` changes associated orders to `EN_RUTA`
- `actual_duration_minutes` used for ML model retraining

---

### 6. `audit_logs`

Comprehensive audit trail for all critical system actions.

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `timestamp` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When action occurred |
| `user_id` | UUID | NULLABLE, FK → users.id | User who acted (NULL for system) |
| `action` | VARCHAR(255) | NOT NULL | Action type |
| `entity_type` | VARCHAR(100) | NOT NULL | Entity affected (ORDER, INVOICE, etc.) |
| `entity_id` | UUID | NULLABLE | ID of affected entity |
| `details` | JSONB | NULLABLE | Action-specific details |
| `result` | ENUM | NOT NULL | SUCCESS, DENIED, ERROR |
| `ip_address` | INET | NULLABLE | Client IP address |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Relationships:**
- Many-to-One with `users`

**Audit Result Enum:**
- `SUCCESS` - Action completed successfully
- `DENIED` - Action denied (business rules or permissions)
- `ERROR` - Action failed due to technical error

**Common Actions:**
- `CREATE_ORDER`
- `TRANSITION_STATE`
- `FORCE_DELIVERY_DATE`
- `CREATE_INVOICE`
- `CREATE_ROUTE`
- `ASSIGN_DRIVER`
- `COMPLETE_DELIVERY`
- `OVERRIDE_CUTOFF`

**Sample Details Structure:**
```json
{
  "old_status": "EN_PREPARACION",
  "new_status": "DOCUMENTADO",
  "invoice_id": "uuid-here",
  "reason": "Invoice linked"
}
```

**Constraints:**
- `FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL`

**Indexes:**
- Primary key on `id`
- Index on `timestamp` (for time-based queries)
- Composite index on `(entity_type, entity_id)` (for entity audit trails)
- Index on `user_id`
- Index on `action`

**Business Rules:**
- All business rule overrides MUST be logged
- Failed permission checks MUST be logged
- State transitions MUST be logged
- Logs are append-only (never deleted or modified)

---

## PostGIS Spatial Queries

The `orders.address_coordinates` column uses PostGIS Geography type with SRID 4326 (WGS84).

### Common Spatial Queries

**1. Calculate distance between two orders (in meters):**
```sql
SELECT ST_Distance(
    o1.address_coordinates,
    o2.address_coordinates
) as distance_meters
FROM orders o1, orders o2
WHERE o1.id = 'uuid1' AND o2.id = 'uuid2';
```

**2. Find orders within 5km radius of a point:**
```sql
SELECT *
FROM orders
WHERE ST_DWithin(
    address_coordinates,
    ST_GeographyFromText('POINT(-70.7407 -34.1704)'),
    5000  -- meters
);
```

**3. Order by distance from warehouse:**
```sql
SELECT order_number, customer_name,
       ST_Distance(
           address_coordinates,
           ST_GeographyFromText('POINT(-70.7350 -34.1650)')
       ) as distance_meters
FROM orders
WHERE delivery_date = CURRENT_DATE
  AND order_status = 'DOCUMENTADO'
ORDER BY distance_meters;
```

---

## Business Rules Implementation

### Cut-off Time Logic

Implemented in application layer with audit logging:

```python
from datetime import datetime, time

MORNING_CUTOFF = time(12, 0)  # 12:00 PM
AFTERNOON_CUTOFF = time(15, 0)  # 3:00 PM

def calculate_delivery_date(order_created_at):
    """
    Determine delivery date based on creation time

    - Orders before 12:00 PM: eligible for same-day
    - Orders after 3:00 PM: next-day delivery
    - Between 12:00-3:00 PM: warehouse decides
    """
    created_time = order_created_at.time()

    if created_time <= MORNING_CUTOFF:
        return order_created_at.date()  # Same day
    elif created_time > AFTERNOON_CUTOFF:
        return order_created_at.date() + timedelta(days=1)  # Next day
    else:
        # Requires manual decision
        return None
```

### Invoice Requirement for Routing

Enforced via database trigger or application logic:

```python
def transition_to_en_ruta(order_id, session):
    """Cannot transition to EN_RUTA without invoice"""
    order = session.get(Order, order_id)

    if not order.invoice:
        raise BusinessRuleViolation(
            "Cannot route order without invoice"
        )

    order.order_status = OrderStatus.EN_RUTA

    # Log the transition
    log = AuditLog(
        action="TRANSITION_STATE",
        entity_type="ORDER",
        entity_id=order.id,
        details={
            "old_status": "DOCUMENTADO",
            "new_status": "EN_RUTA",
            "invoice_number": order.invoice.invoice_number
        },
        result=AuditResult.SUCCESS
    )
    session.add(log)
```

---

## Scalability Considerations

### Current Scale (Phase 1)
- **Orders:** ~100-500 per day
- **Active Routes:** ~5-20 per day
- **Users:** ~10-50 users
- **Geographic Area:** Rancagua and surroundings (~50km radius)

### Optimization Strategies

**1. Partitioning (Future):**
- Partition `orders` table by `delivery_date` (monthly partitions)
- Partition `audit_logs` by `timestamp` (monthly partitions)

**2. Archival Strategy:**
- Move orders older than 6 months to `orders_archive` table
- Move audit logs older than 1 year to cold storage

**3. Indexes:**
- Already implemented spatial GIST index for geographic queries
- Composite indexes on frequently queried combinations

**4. Caching:**
- Cache active routes in Redis
- Cache user permissions in Redis (invalidate on role change)

**5. Read Replicas (Future):**
- Route reporting queries to read replica
- Master handles all writes

---

## Migration History

### Migration 001: Initial Schema (2026-01-20)

Created all core tables:
- `roles`
- `users`
- `orders` (with PostGIS)
- `invoices`
- `routes`
- `audit_logs`

Created all PostgreSQL enums:
- `order_status_enum`
- `source_channel_enum`
- `geocoding_confidence_enum`
- `invoice_type_enum`
- `route_status_enum`
- `audit_result_enum`

Enabled PostGIS extension.

---

## Security Considerations

1. **Password Storage:** All passwords stored as BCrypt hashes (never plaintext)
2. **Role-Based Access:** All actions checked against `permissions` JSONB
3. **Audit Trail:** All sensitive actions logged to `audit_logs`
4. **SQL Injection Prevention:** Using SQLAlchemy ORM with parameterized queries
5. **Foreign Key Constraints:** Prevent orphaned records and maintain referential integrity

---

## Backup Strategy

**Daily Backups:**
```bash
pg_dump -Fc claude_logistics > backup_$(date +%Y%m%d).dump
```

**Point-in-Time Recovery:**
Enable WAL archiving for PostgreSQL to support PITR.

**Retention:**
- Daily backups: 30 days
- Monthly backups: 1 year
- Critical data (orders, invoices): permanent archive

---

## Performance Benchmarks

Target query performance (to be measured post-deployment):

- Order creation: < 100ms
- Route optimization (20 stops): < 5 seconds
- Distance calculations (100 orders): < 500ms
- Audit log queries: < 200ms

---

## Contact & Maintenance

**Database Schema Version:** 1.0.0
**Last Updated:** 2026-01-20
**Migration Tool:** Alembic
**ORM:** SQLAlchemy 2.0+

For schema changes, always use Alembic migrations to maintain version control and enable rollback capabilities.
