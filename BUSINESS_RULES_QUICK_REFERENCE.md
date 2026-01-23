# BUSINESS RULES - QUICK REFERENCE GUIDE
## Sistema de Gestión de Despachos Logísticos

**For:** Developers implementing FASE 2
**Version:** 1.0.0
**Date:** 2026-01-21

---

## Critical Business Rules Summary

### Cut-off Times (BR-001, BR-002, BR-003)

| Time | Delivery Date | Rule | Override |
|------|---------------|------|----------|
| <= 12:00:00 | Same day (if business day) | BR-001 | Admin only |
| 12:00:01 - 15:00:00 | Same day (flexible) | BR-003 | Encargado/Admin |
| > 15:00:00 | Next business day | BR-002 | Admin only |

**Weekend/Holiday:** Always next business day

**Timezone:** America/Santiago (MANDATORY)

---

### Invoice Requirements (BR-004, BR-005)

**BR-004:** Order CANNOT be routed without invoice_id

**BR-005:** Creating invoice AUTO-transitions order to DOCUMENTADO

```python
# Before routing
if order.invoice_id is None:
    raise ValidationError("INVOICE_REQUIRED_FOR_ROUTING")
```

---

### State Transitions Quick Reference

#### Valid Transitions

| From | To | Who | Prerequisite |
|------|----|----|--------------|
| PENDIENTE | EN_PREPARACION | Vendedor, Encargado, Admin | delivery_date set |
| EN_PREPARACION | DOCUMENTADO | System (auto) | invoice_id set |
| DOCUMENTADO | EN_RUTA | Encargado, Admin | route assigned & active |
| EN_RUTA | ENTREGADO | Repartidor (own), Admin | - |
| EN_RUTA | INCIDENCIA | Repartidor (own), Admin | reason required |
| INCIDENCIA | EN_RUTA | Encargado, Admin | - |
| INCIDENCIA | DOCUMENTADO | Encargado, Admin | - |

#### Forbidden Transitions

- **ENTREGADO → ANY:** Final state, no transitions out
- **Any backward transition** (except INCIDENCIA → DOCUMENTADO/EN_RUTA)

---

### Permission Matrix (RBAC)

| Action | Admin | Encargado | Vendedor | Repartidor |
|--------|-------|-----------|----------|------------|
| create_order | ✅ | ✅ | ✅ | ❌ |
| view_order | ✅ All | ✅ All | ✅ Own | ✅ Assigned |
| create_invoice | ✅ | ✅ | ✅ | ❌ |
| generate_route | ✅ | ✅ | ❌ | ❌ |
| activate_route | ✅ | ✅ | ❌ | ❌ |
| transition_to_ENTREGADO | ✅ | ❌ | ❌ | ✅ Own route |
| override_cutoff | ✅ | ❌ | ❌ | ❌ |

---

## Implementation Checklist

### Phase 2 - Core Services

- [ ] **CutoffService** (`app/services/cutoff_service.py`)
  - [ ] `calculate_delivery_date()` with timezone handling
  - [ ] `BusinessDayService.is_business_day()`
  - [ ] `BusinessDayService.next_business_day()`
  - [ ] Admin override with audit

- [ ] **InvoiceService** (`app/services/invoice_service.py`)
  - [ ] `create_invoice()` with auto-transition
  - [ ] Validation: unique invoice_number, valid order_id

- [ ] **OrderService** (`app/services/order_service.py`)
  - [ ] `create_order()` with delivery_date calculation
  - [ ] `transition_state()` with validation matrix
  - [ ] Optimistic locking (updated_at check)

- [ ] **PermissionService** (`app/services/permission_service.py`)
  - [ ] `check_permission()` with RBAC matrix
  - [ ] Resource-level scope (own, assigned_routes)
  - [ ] Audit logging for denials

- [ ] **AuditService** (`app/services/audit_service.py`)
  - [ ] `log()` method with structured JSONB details
  - [ ] Automatic logging for critical actions

- [ ] **RouteService** (`app/services/route_service.py`)
  - [ ] `generate_route()` filtering eligible orders
  - [ ] `activate_route()` transitioning orders to EN_RUTA
  - [ ] Validation: driver assigned, stop_sequence valid

- [ ] **ValidationService** (`app/services/validation_service.py`)
  - [ ] `validate_order_for_routing()`
  - [ ] Geocoding quality check (BR-020)
  - [ ] Business day validation

---

## Error Handling Quick Reference

### HTTP Status Codes

| Error Type | HTTP Status | Example Code |
|------------|-------------|--------------|
| Validation failed | 400 | INVOICE_REQUIRED_FOR_ROUTING |
| Permission denied | 403 | INSUFFICIENT_PERMISSIONS |
| Not found | 404 | ORDER_NOT_FOUND |
| Concurrent modification | 409 | CONCURRENT_MODIFICATION |
| Server error | 500 | INTERNAL_SERVER_ERROR |

### Common Error Codes

```python
# Validation Errors (400)
INVOICE_REQUIRED_FOR_ROUTING
INVALID_STATE_TRANSITION
CUTOFF_TIME_VIOLATION
INCIDENCE_REASON_REQUIRED
INVALID_DELIVERY_DATE

# Permission Errors (403)
INSUFFICIENT_PERMISSIONS
ADMIN_OVERRIDE_REQUIRED
NOT_YOUR_ROUTE
NOT_YOUR_ORDER

# Concurrency Errors (409)
CONCURRENT_MODIFICATION
ROUTE_ALREADY_ACTIVE
```

---

## Audit Logging Standards

### Critical Actions (MUST log)

- All state transitions
- All permission denials
- All admin overrides
- Route generation/activation
- Invoice creation

### Audit Log Structure

```python
AuditService.log(
    action='TRANSITION_EN_RUTA',          # Action name
    entity_type='ORDER',                   # ORDER, INVOICE, ROUTE, USER
    entity_id=order.id,                    # UUID of affected entity
    user_id=current_user.id,               # UUID of user (null for system)
    result=AuditResult.SUCCESS,            # SUCCESS, DENIED, ERROR
    details={                              # JSONB - action-specific
        'previous_status': 'DOCUMENTADO',
        'new_status': 'EN_RUTA',
        'route_id': str(route.id)
    }
)
```

---

## Testing Priorities

### Critical Tests (P0 - Must Pass)

1. **Cut-off boundary tests**
   - `test_cutoff_am_boundary_exactly_noon()`
   - `test_cutoff_pm_one_second_after_3pm()`
   - `test_cutoff_friday_after_3pm()`

2. **Invoice requirement tests**
   - `test_invoice_required_routing()`
   - `test_auto_transition_documentado()`

3. **Permission tests**
   - `test_vendedor_view_own_orders_only()`
   - `test_repartidor_deliver_own_route_only()`
   - `test_admin_override_cutoff()`

4. **State transition tests**
   - `test_complete_order_lifecycle()`
   - `test_backward_transition_denied()`
   - `test_incidence_and_retry_flow()`

### High Priority Tests (P1 - Should Pass)

5. **Concurrency tests**
   - `test_concurrent_state_change()`
   - `test_optimistic_locking()`

6. **Edge case tests**
   - `test_weekend_delivery_date()`
   - `test_geocoding_low_quality_routing()`
   - `test_duplicate_invoice_number()`

---

## Code Snippets

### 1. Calculate Delivery Date

```python
from app.services.cutoff_service import CutoffService
from datetime import datetime
from zoneinfo import ZoneInfo

created_at = datetime.now(ZoneInfo("America/Santiago"))

delivery_date = CutoffService.calculate_delivery_date(
    order_created_at=created_at,
    user=current_user,
    override_date=None,      # Admin only
    override_reason=None
)
```

### 2. Transition Order State

```python
from app.services.order_service import OrderService

order = OrderService.transition_state(
    order_id=order_id,
    target_status=OrderStatus.EN_RUTA,
    user=current_user,
    incidence_reason=None,   # Required for INCIDENCIA
    db=db_session
)
```

### 3. Check Permission

```python
from app.services.permission_service import PermissionService

try:
    PermissionService.check_permission(
        user=current_user,
        action='transition_to_EN_RUTA',
        resource=order  # Optional, for resource-level checks
    )
except PermissionError as e:
    raise HTTPException(status_code=403, detail=str(e))
```

### 4. Create Invoice with Auto-Transition

```python
from app.services.invoice_service import InvoiceService

invoice = InvoiceService.create_invoice(
    order_id=order.id,
    invoice_number="FACT-2026-001",
    invoice_type=InvoiceType.FACTURA,
    total_amount=50000.00,
    user=current_user,
    db=db_session
)

# Order automatically transitions to DOCUMENTADO (BR-005)
db_session.refresh(order)
assert order.order_status == OrderStatus.DOCUMENTADO
```

### 5. Validate Order for Routing

```python
from app.services.validation_service import ValidationService

try:
    ValidationService.validate_order_for_routing(order)
except ValidationError as e:
    # Handle: invoice missing, wrong state, low geocoding quality
    raise HTTPException(status_code=400, detail=str(e))
```

---

## Database Queries

### Get Eligible Orders for Route

```python
from app.models.enums import OrderStatus, GeocodingConfidence

eligible_orders = db.query(Order).filter(
    Order.order_status == OrderStatus.DOCUMENTADO,
    Order.delivery_date == target_date,
    Order.assigned_route_id.is_(None),
    Order.invoice_id.isnot(None),
    Order.geocoding_confidence.in_([
        GeocodingConfidence.HIGH,
        GeocodingConfidence.MEDIUM
    ])
).all()
```

### Get User's Orders (Vendedor - own only)

```python
if current_user.role.role_name == 'Vendedor':
    orders = db.query(Order).filter(
        Order.created_by_user_id == current_user.id
    ).all()
```

### Get Repartidor's Assigned Orders

```python
if current_user.role.role_name == 'Repartidor':
    orders = db.query(Order).join(Route).filter(
        Route.assigned_driver_id == current_user.id,
        Order.assigned_route_id == Route.id
    ).all()
```

---

## Common Pitfalls & Solutions

### 1. Timezone Issues

**Problem:** Order created at 11:59 AM UTC → Treated as 8:59 AM Chile → Wrong delivery date

**Solution:** ALWAYS use America/Santiago timezone

```python
# WRONG
created_at = datetime.now()  # Uses system timezone

# CORRECT
from zoneinfo import ZoneInfo
created_at = datetime.now(ZoneInfo("America/Santiago"))
```

### 2. Forgetting Invoice Validation

**Problem:** Order added to route without invoice → Route fails to activate

**Solution:** Validate invoice_id before ANY routing operation

```python
if order.invoice_id is None:
    raise ValidationError("INVOICE_REQUIRED_FOR_ROUTING")
```

### 3. Permission Checks Only at API Layer

**Problem:** Service methods called directly bypass permission checks

**Solution:** Check permissions in BOTH API and Service layers

```python
# In API endpoint
PermissionService.check_permission(user, 'create_order')

# In Service method (defensive)
if not user.role.role_name in ['Administrador', 'Vendedor']:
    raise PermissionError("INSUFFICIENT_PERMISSIONS")
```

### 4. Not Handling Concurrency

**Problem:** Two users transition same order → Data inconsistency

**Solution:** Use optimistic locking

```python
# Check updated_at before update
rows_affected = db.query(Order).filter(
    Order.id == order_id,
    Order.updated_at == expected_updated_at
).update({'order_status': new_status})

if rows_affected == 0:
    raise ConcurrencyError("CONCURRENT_MODIFICATION")
```

### 5. Missing Audit Logs

**Problem:** Critical actions not logged → No compliance trail

**Solution:** Log ALL critical actions explicitly

```python
from app.services.audit_service import AuditService

# After successful state transition
AuditService.log(
    action='TRANSITION_EN_RUTA',
    entity_type='ORDER',
    entity_id=order.id,
    user_id=user.id,
    result=AuditResult.SUCCESS,
    details={'previous_status': old_status, 'new_status': new_status}
)
```

---

## Performance Considerations

### 1. Database Indexes

Ensure these indexes exist:

```sql
-- Order queries
CREATE INDEX ix_orders_order_status ON orders(order_status);
CREATE INDEX ix_orders_delivery_date ON orders(delivery_date);
CREATE INDEX ix_orders_created_by_user_id ON orders(created_by_user_id);

-- Spatial queries
CREATE INDEX ix_orders_address_coordinates ON orders USING GIST(address_coordinates);

-- Audit log queries
CREATE INDEX ix_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX ix_audit_logs_entity_type_entity_id ON audit_logs(entity_type, entity_id);
```

### 2. Batch Operations

When activating route with 50+ orders:

```python
# Use bulk_update instead of individual commits
db.bulk_update_mappings(Order, [
    {'id': order_id, 'order_status': OrderStatus.EN_RUTA}
    for order_id in route.stop_sequence
])
db.commit()
```

### 3. Audit Log Async Writing

For high-volume operations, write audit logs asynchronously:

```python
# Queue audit log for async processing
audit_queue.enqueue(
    'log_audit_entry',
    action=action,
    details=details
)
```

---

## Deployment Checklist

Before deploying to production:

- [ ] All P0 tests passing
- [ ] Timezone set to America/Santiago in server config
- [ ] Chilean holidays list updated for current year
- [ ] Database indexes created
- [ ] Audit log retention policy configured
- [ ] Error monitoring configured (Sentry, etc.)
- [ ] Performance benchmarks validated
- [ ] Permission matrix reviewed with stakeholders
- [ ] Documentation updated

---

## Support & Resources

**Full Specification:** `/home/juan/Desarrollo/route_dispatch/BUSINESS_RULES_FORMAL_SPEC.md`

**Code Examples:** `/home/juan/Desarrollo/route_dispatch/BUSINESS_RULES_EXAMPLES.md`

**Data Models:** `/home/juan/Desarrollo/route_dispatch/app/models/models.py`

**Enums:** `/home/juan/Desarrollo/route_dispatch/app/models/enums.py`

---

**Last Updated:** 2026-01-21 by business-policy-architect
