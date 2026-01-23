# Test Suite Documentation - Claude Logistics API

This directory contains comprehensive test suites for the Claude Logistics API, covering security, business rules, performance, and edge cases.

---

## Test Organization

```
tests/
├── README.md                          # This file
├── conftest.py                        # Global fixtures
├── test_business_rules/               # Business rule compliance tests
│   ├── conftest.py                    # BR-specific fixtures (30+)
│   ├── test_cutoff_boundary.py        # BR-001/002/003: Cutoff times
│   ├── test_invoice_requirements.py   # BR-004/005: Invoice requirements
│   └── test_state_transitions.py      # BR-006-013: State machine
├── test_security/                     # Security vulnerability tests
│   ├── test_authorization_boundaries.py  # RBAC enforcement
│   ├── test_injection_attacks.py         # SQL injection, XSS
│   └── test_password_token_security.py   # Auth security
├── test_performance/                  # Performance benchmarks
│   ├── conftest.py                    # Performance fixtures
│   ├── test_route_generation_performance.py
│   └── test_database_query_performance.py
├── test_edge_cases/                   # Edge case handling
│   ├── test_null_empty_inputs.py
│   └── test_external_service_failures.py
├── test_api/                          # API endpoint tests
│   ├── conftest.py
│   ├── test_auth_endpoints.py
│   ├── test_orders_endpoints.py
│   └── test_invoices_endpoints.py
├── test_services/                     # Service layer tests
│   ├── test_auth_service.py
│   ├── test_cutoff_service.py
│   ├── test_geocoding_service.py
│   └── ...
└── test_integration/                  # Integration tests
    └── test_order_notification_integration.py
```

---

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-xdist

# Start PostgreSQL with PostGIS
docker-compose up -d postgres

# Run migrations
alembic upgrade head
```

### Run All Tests

```bash
# Run complete test suite
pytest tests/ -v

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term tests/

# Run in parallel (faster)
pytest tests/ -n auto -v
```

### Run Specific Test Categories

```bash
# Business rule tests
pytest tests/test_business_rules/ -v

# Security tests
pytest tests/test_security/ -v

# Performance tests
pytest tests/test_performance/ -v

# Edge case tests
pytest tests/test_edge_cases/ -v
```

---

## Test Categories

### 1. Business Rules Tests (`test_business_rules/`)

Tests verifying compliance with business requirements (BR-001 to BR-026).

#### Cutoff Time Tests (`test_cutoff_boundary.py`)

**Coverage**: BR-001, BR-002, BR-003, BR-017

**Critical Test Cases**:
- ✅ Order at exactly 12:00:00 → same day delivery
- ✅ Order at 11:59:59 → same day delivery
- ✅ Order at 12:00:01 → same day delivery (flexible window)
- ✅ Order at exactly 15:00:00 → same day delivery
- ✅ Order at 15:00:01 → next business day delivery
- ✅ Weekend and holiday handling
- ✅ Admin override with valid reason
- ✅ Non-admin override rejected

**Run Tests**:
```bash
pytest tests/test_business_rules/test_cutoff_boundary.py -v
```

---

#### Invoice Requirement Tests (`test_invoice_requirements.py`)

**Coverage**: BR-004, BR-005, BR-015

**Critical Test Cases**:
- ✅ Cannot transition to EN_RUTA without invoice
- ✅ Creating invoice auto-transitions to DOCUMENTADO
- ✅ Cannot create duplicate invoice for same order
- ✅ Invoice number must be unique across all orders
- ✅ Invoice amount must be positive (no negatives, no zeros)
- ✅ Vendedor can create invoices, Repartidor cannot

**Run Tests**:
```bash
pytest tests/test_business_rules/test_invoice_requirements.py -v
```

---

#### State Transition Tests (`test_state_transitions.py`)

**Coverage**: BR-006 to BR-013, BR-022, BR-023

**Critical Test Cases**:
- ✅ All valid transitions allowed (6 paths)
- ✅ All invalid transitions blocked (15+ combinations)
- ✅ ENTREGADO is final state (no transitions out)
- ✅ EN_RUTA requires invoice and active route
- ✅ INCIDENCIA requires reason
- ✅ Repartidor can only mark own routes as ENTREGADO
- ✅ Concurrent transitions use pessimistic locking
- ✅ Idempotent transitions (safe to retry)

**Run Tests**:
```bash
pytest tests/test_business_rules/test_state_transitions.py -v
```

---

### 2. Security Tests (`test_security/`)

Tests verifying security vulnerabilities and attack prevention.

#### Authorization Boundary Tests (`test_authorization_boundaries.py`)

**Coverage**: RBAC, privilege escalation prevention

**Critical Test Cases**:
- ✅ Repartidor cannot create users (403 Forbidden)
- ✅ Vendedor cannot create users
- ✅ Vendedor can only view own orders (NotYourOrderError)
- ✅ Repartidor can only view assigned routes (NotYourRouteError)
- ✅ Admin can bypass all resource ownership restrictions
- ✅ Permission denials logged in audit trail

**Security Impact**: **CRITICAL** - Prevents privilege escalation

**Run Tests**:
```bash
pytest tests/test_security/test_authorization_boundaries.py -v
```

---

#### Injection Attack Tests (`test_injection_attacks.py`)

**Coverage**: SQL injection, XSS, command injection

**Critical Test Cases**:
- ✅ SQL injection in customer_name: `'; DROP TABLE orders; --`
- ✅ SQL injection in address: `' OR '1'='1`
- ✅ SQL injection in invoice_number
- ✅ XSS script tags: `<script>alert('XSS')</script>`
- ✅ XSS with event handlers: `<img src=x onerror=alert()>`
- ✅ Command injection: `; rm -rf / ;`
- ✅ Path traversal: `../../etc/passwd`
- ✅ Unicode and special characters handled correctly

**Security Impact**: **CRITICAL** - Prevents code execution and data theft

**Run Tests**:
```bash
pytest tests/test_security/test_injection_attacks.py -v
```

---

#### Password & Token Security Tests (`test_password_token_security.py`)

**Coverage**: Password hashing, JWT security

**Critical Test Cases**:
- ✅ Passwords hashed with BCrypt (work factor 12)
- ✅ Password hash never exposed in API responses
- ✅ Expired tokens rejected (TokenExpiredError)
- ✅ Tampered tokens rejected (signature validation)
- ✅ Refresh tokens revoked on logout
- ✅ Revoked refresh tokens rejected
- ✅ Tokens for inactive users rejected
- ✅ Audit logs don't expose full tokens

**Security Impact**: **CRITICAL** - Prevents credential theft

**Run Tests**:
```bash
pytest tests/test_security/test_password_token_security.py -v
```

---

### 3. Performance Tests (`test_performance/`)

Tests establishing performance baselines and identifying bottlenecks.

#### Route Generation Performance (`test_route_generation_performance.py`)

**Target**: BR-024 compliance (< 15s for 50 orders)

**Test Cases**:
- ⏳ Route generation for 50 orders (< 15s)
- ⏳ Route generation for 100 orders (< 30s)
- ⏳ Scalability testing (10, 20, 30 orders)
- ⏳ Distance matrix calculation (< 5s for 50x50)
- ⏳ TSP solver performance (< 10s for 50 nodes)

**Run Tests**:
```bash
pytest tests/test_performance/test_route_generation_performance.py -v --durations=10
```

**Note**: Requires PostgreSQL with PostGIS. Tests marked with `@pytest.mark.performance`.

---

#### Database Query Performance (`test_database_query_performance.py`)

**Target**: P95 latency < 200ms for critical queries

**Test Cases**:
- ⏳ List orders query (P95 < 200ms)
- ⏳ Get order with relationships (P95 < 200ms)
- ⏳ Orders for delivery date query (< 300ms)
- ⏳ PostGIS distance calculation (P95 < 10ms)
- ⏳ Concurrent order creation (no race conditions)
- ⏳ Concurrent state transitions (pessimistic locking)

**Run Tests**:
```bash
pytest tests/test_performance/test_database_query_performance.py -v
```

---

### 4. Edge Case Tests (`test_edge_cases/`)

Tests verifying graceful handling of unusual inputs and failures.

#### Null & Empty Input Tests (`test_null_empty_inputs.py`)

**Test Cases**:
- ✅ Null customer_name rejected (ValidationError)
- ✅ Empty strings rejected
- ✅ Whitespace-only inputs rejected
- ✅ Invalid UUIDs rejected
- ✅ Non-Chilean phone formats rejected
- ✅ Negative invoice amounts rejected
- ✅ Zero invoice amounts rejected
- ✅ Very long inputs (10,000 chars) handled gracefully

**Run Tests**:
```bash
pytest tests/test_edge_cases/test_null_empty_inputs.py -v
```

---

#### External Service Failure Tests (`test_external_service_failures.py`)

**Test Cases**:
- ✅ Geocoding API timeout returns error result (no exception)
- ✅ Geocoding connection error handled gracefully
- ✅ Nominatim empty response returns INVALID confidence
- ✅ Low confidence geocoding rejected
- ✅ SMTP authentication failure returns False (no exception)
- ✅ Email timeout handled gracefully
- ✅ Notification failure doesn't block order transition
- ✅ Failed geocoding results cached (avoid repeated API calls)

**Security Impact**: **MEDIUM** - Ensures graceful degradation

**Run Tests**:
```bash
pytest tests/test_edge_cases/test_external_service_failures.py -v
```

---

## Test Fixtures

### Global Fixtures (`conftest.py`)

- `client`: FastAPI TestClient
- `chile_timezone`: ZoneInfo("America/Santiago")
- `mock_admin_user`, `mock_vendedor_user`, etc.
- `db_engine`, `db_session`: SQLite in-memory database

### Business Rules Fixtures (`test_business_rules/conftest.py`)

**30+ fixtures including**:
- Users: `admin_user`, `vendedor_user`, `encargado_user`, `repartidor_user`
- Roles: `admin_role`, `vendedor_role`, etc.
- Orders in all states: `sample_order_pendiente`, `sample_order_en_ruta`, etc.
- Invoices: `sample_invoice`, `invoice_created_by_another_vendedor`
- Routes: `sample_route_draft`, `sample_route_active`, `route_assigned_to_repartidor`
- Ownership: `order_created_by_vendedor`, `order_created_by_other_vendedor`

### Performance Fixtures (`test_performance/conftest.py`)

- `db_session_factory`: Creates new DB sessions for concurrent tests
- `create_bulk_orders`: Factory for creating N orders

---

## Test Markers

Tests are organized using pytest markers for selective execution:

```python
@pytest.mark.performance  # Performance tests
@pytest.mark.slow         # Slow-running tests (> 5s)
@pytest.mark.security     # Security-specific tests
```

### Run Tests by Marker

```bash
# Run only performance tests
pytest -m performance -v

# Run only slow tests
pytest -m slow -v

# Run security tests
pytest -m security -v

# Exclude slow tests
pytest -m "not slow" -v
```

---

## Coverage Reports

### Generate Coverage Report

```bash
# Run tests with coverage
pytest --cov=app --cov-report=html --cov-report=term tests/

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Target Coverage

| Module | Target | Critical Paths |
|--------|--------|----------------|
| `auth_service.py` | 90%+ | Login, token validation |
| `order_service.py` | 85%+ | State transitions |
| `permission_service.py` | 95%+ | RBAC matrix |
| `cutoff_service.py` | 95%+ | Boundary conditions |
| `invoice_service.py` | 90%+ | Auto-transition |

**Overall Target**: ≥ 85% for critical business logic

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgis/postgis:14-3.2
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: |
          pytest tests/ -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Troubleshooting

### Database Connection Issues

```bash
# Verify PostgreSQL is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### Test Failures

```bash
# Run specific failing test with verbose output
pytest tests/path/to/test.py::TestClass::test_method -vv

# Run with print statements visible
pytest tests/ -v -s

# Run with pdb debugger on failure
pytest tests/ -v --pdb
```

### Slow Tests

```bash
# See which tests are slowest
pytest tests/ --durations=20

# Run fast tests only
pytest tests/ -m "not slow" -v
```

---

## Best Practices

### Writing New Tests

1. **Use descriptive test names**: `test_vendedor_cannot_view_other_vendedor_order`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Use appropriate fixtures**: Prefer existing fixtures over creating new data
4. **Test one thing**: Each test should verify a single behavior
5. **Use markers**: Mark performance tests, slow tests, etc.

### Example Test Structure

```python
def test_business_rule_enforcement(db_session, admin_user, sample_order):
    """
    Test BR-XXX: Brief description of business rule

    Expected: Specific expected behavior
    """
    # Arrange
    service = OrderService(db_session)

    # Act
    result = service.some_operation(sample_order, admin_user)

    # Assert
    assert result.status == ExpectedStatus
    assert result.some_field == expected_value
```

---

## Test Statistics

### Test Count by Category

- **Business Rules**: 73+ tests
- **Security**: 80+ tests
- **Performance**: 14 tests
- **Edge Cases**: 40+ tests
- **API Endpoints**: 20+ tests
- **Services**: 30+ tests
- **Integration**: 5+ tests

**Total**: 250+ test cases

### Test File Count

- Test files: 15+
- Fixture files: 3
- Total lines of test code: ~4,000+

---

## Additional Resources

- **Security Audit Report**: `/SECURITY_AUDIT_REPORT.md`
- **Performance Baseline**: `/PERFORMANCE_BASELINE.md`
- **Phase 8 Summary**: `/PHASE_8_SUMMARY.md`
- **Business Rules Spec**: `/BUSINESS_RULES_FORMAL_SPEC.md`
- **API Endpoints**: `/API_ENDPOINTS_REFERENCE.md`

---

## Maintenance

### Updating Tests

When business rules change:
1. Update test expectations
2. Update fixtures if needed
3. Re-run full test suite
4. Update documentation

### Adding New Tests

When adding new features:
1. Add business rule tests
2. Add security tests (authorization, input validation)
3. Add performance tests if critical path
4. Add edge case tests
5. Update fixtures as needed

---

**Test Suite Maintained By**: QA Team
**Last Updated**: January 22, 2026
**Test Framework**: pytest 7.x
**Python Version**: 3.11+
