# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is "Claude" - an AI-powered logistics and last-mile delivery management system designed for a **botillería** (liquor store) in Rancagua, Chile. The system automates the complete order lifecycle from ingestion to final delivery using a multi-agent architecture where specialized agents coordinate to manage logistics, optimize routes, enforce business policies, and communicate with customers.

**Business Domain**: Liquor retail with delivery services
**Geographic Context**: Rancagua, Chile and surrounding areas (Machalí and periphery)
**Core Focus Areas**:
- Route automation for delivery optimization
- Cut-off time enforcement for same-day/next-day delivery eligibility
- Invoice traceability and billing compliance

## Technology Stack

- **Primary Language**: Python (for AI, data science, and optimization using Google OR-Tools, Pandas)
- **API Framework**: FastAPI (high-performance service endpoints)
- **Database**: PostgreSQL with PostGIS extension (geospatial data and distance calculations)

## Multi-Agent Architecture

The system is built on a coordinated multi-agent model where each agent has a specific domain expertise:

### Core Agents

1. **workflow-orchestrator** (red): Coordinates the entire workflow, manages order state transitions, activates other agents based on state changes, generates compliance reports
2. **route-optimizer** (pink): Solves Traveling Salesperson Problem (TSP) variations, optimizes delivery routes considering traffic, time windows, and geographic constraints
3. **business-policy-architect** (green): Translates business requirements into implementable logic, enforces business rules (like cut-off times), defines access control frameworks
4. **business-logic-developer**: Implements services, state management, external API integrations (mapping services), internal admin interfaces (user management)
5. **data-architecture-validator**: Ensures database schema integrity, validates entity relationships, assesses scalability
6. **geocoding-data-validator**: Converts addresses to coordinates, validates address quality, rejects ambiguous location data
7. **customer-notification-ux**: Manages outbound customer communications (WhatsApp, Email) when orders transition to "En Ruta" state
8. **qa-security-tester**: Tests business logic, validates security, identifies edge cases and vulnerabilities
9. **devops-infrastructure-manager**: Manages infrastructure (Supabase, AWS), deployment, secure API access

### Agent Coordination

- The **workflow-orchestrator** acts as the central nervous system, detecting state changes and activating appropriate agents
- State transitions trigger specific agent activations (e.g., "Documentado" state → route-optimizer agent)
- All critical actions must be logged for audit trails

## Critical Business Rules

These rules form the foundation of the system's business logic, particularly around **route automation**, **cut-off time control**, and **invoice traceability**.

### 1. Delivery Cut-off Times (Enforced by business-policy-architect)

**AM Rule**: Orders placed by 12:00 PM → eligible for same-day delivery
**PM Rule**: Orders placed after 3:00 PM → next-day delivery only

- Vendors cannot override these rules without explicit Administrator authorization
- All override attempts must be logged in audit trail with timestamp, user, action, and result

### 2. Invoice Requirement (Invoice Traceability)

**Critical Validation**: No order can be included in a delivery route without an associated invoice (factura/boleta). This ensures complete billing traceability.

- State transition: When invoice is linked → order changes from "En Preparación" to "Documentado"
- Only "Documentado" orders are eligible for route optimization

### 3. Order Lifecycle States

1. **Pendiente**: Newly created order
2. **En Preparación**: Being prepared in warehouse (picking)
3. **Documentado**: Invoice linked - CRITICAL state that enables dispatch
4. **En Ruta**: Assigned to vehicle, departed from warehouse (triggers customer notification)
5. **Entregado**: Delivery confirmed by driver
6. **Incidencia**: Delivery could not be completed

## Data Model Core Entities

- **Orders (Pedidos)**: Contains purchase timestamp, address, customer, state
- **Invoices (Facturas)**: Fiscal document number, direct relationship to Order
- **Routes (Rutas)**: Generated routes, stop sequence, estimated vs actual times (for ML re-training)
- **Users (Usuarios)**: ID/UUID, Username/Email, Password Hash (Argon2/BCrypt), Role_ID, Active_Status

## User Roles & Permissions

- **Warehouse Manager (Encargado de Bodega)**: Supervises process, validates documentation, authorizes routes proposed by Claude
- **Vendors (Vendedores)**: Create orders, subject to business rule enforcement
- **Delivery Drivers (Repartidores)**: Consume optimized routes via mobile interface, update delivery status

## Route Optimization Algorithm (Route Automation)

The route-optimizer agent automates delivery route planning to minimize travel time and distance.

**Inputs**:
- Delivery coordinates (lat/long)
- Vehicle capacity
- Time windows
- Real-time or historical traffic data
- Rancagua geographic context

**Output**:
- Ordered sequence of deliveries minimizing distance/time for each vehicle

**Context**: Algorithm must be parameterized for Rancagua geography and traffic patterns

## Audit & Compliance

All critical actions must generate audit logs:
```
[Timestamp] | Action: "Change delivery date" | User: "Vendor_01" | Detail: "Attempted same-day delivery for order #123 at 16:00" | Result: "DENIED"
```

## Development Commands

This project is currently in specification phase. Implementation commands will be added as code is developed.

## Working with Claude Code Agents

When developing features for this system:

1. **State Changes**: Use workflow-orchestrator agent to manage order state transitions
2. **Route Planning**: Use route-optimizer agent for TSP problems and delivery sequencing
3. **Business Rules**: Use business-policy-architect agent to translate requirements into implementable logic
4. **Data Validation**: Use geocoding-data-validator agent for address processing
5. **Security Review**: Use qa-security-tester agent after implementing authentication, authorization, or data validation logic
6. **Infrastructure**: Use devops-infrastructure-manager agent for deployment and cloud resource configuration

## Key Technical Considerations

- **Security**: Implement secure password hashing (Argon2/BCrypt), role-based access control, audit logging
- **Geospatial**: Leverage PostGIS for native geographic calculations
- **State Management**: Use atomic state updates to prevent race conditions
- **Optimization**: Consider problem size when choosing algorithms (exact vs heuristic approaches)
- **Validation**: Validate data at system boundaries (user input, external APIs) but trust internal code

## Documentation References

See CLAUDE_IA_SPEC.md for complete system specification including detailed agent responsibilities, business requirements, and architectural decisions.
