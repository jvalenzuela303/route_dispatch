# Documento de Especificación de Desarrollo: IA "Claude" para Gestión de Despachos

## 1. Introducción y Visión General

### 1.1. Propósito
Este documento detalla las especificaciones técnicas y funcionales para el desarrollo e implementación del sistema de inteligencia artificial "Claude". Claude está diseñado para ser el núcleo centralizado que gestiona, optimiza y automatiza el ciclo de vida completo de los despachos de la empresa, desde la ingesta del pedido hasta la entrega final al cliente.

### 1.2. Visión del Sistema
Claude operará como un sistema basado en agentes, donde cada componente especializado se encarga de una fase específica del proceso logístico. El objetivo es mejorar la eficiencia operativa, reducir errores manuales, garantizar el cumplimiento de las reglas de negocio y mejorar la experiencia del cliente a través de una gestión de rutas inteligente y una comunicación proactiva.

### 1.3. Objetivos de Negocio
- **Automatizar** la asignación de fechas de entrega según reglas de horario estrictas.
- **Optimizar** las rutas de reparto para minimizar tiempos y costos.
- **Garantizar** la integridad del proceso, asegurando que cada despacho esté debidamente facturado.
- **Proveer** trazabilidad y auditoría sobre las operaciones y decisiones del sistema.
- **Mejorar** la comunicación y satisfacción del cliente final.

## 2. Arquitectura General del Sistema

### 2.1. Modelo de Agentes
Claude se fundamenta en una arquitectura de múltiples agentes, coordinados por un orquestador central. Cada agente es un experto en su dominio y colabora para cumplir el flujo operativo completo.

### 2.2. Flujo de Datos General
1.  **Ingesta**: Los pedidos son recibidos desde múltiples canales (Web, RRSS, Presencial).
2.  **Validación**: Claude aplica reglas de negocio (ej. ventana temporal) y valida la calidad de los datos (ej. dirección).
3.  **Consolidación**: El sistema facilita la vinculación de documentos fiscales (facturas) a los pedidos.
4.  **Optimización**: Un agente especializado calcula la ruta de entrega más eficiente para los pedidos listos.
5.  **Despacho**: El estado del pedido se actualiza a "En Ruta" y se notifican a los clientes.
6.  **Seguimiento**: El sistema monitorea el progreso de las entregas.

### 2.3. Stack Tecnológico Recomendado
- **Lenguaje Principal**: **Python**, por su robusto ecosistema de librerías para IA, ciencia de datos y optimización (e.g., Google OR-Tools, Pandas).
- **Framework de API**: **FastAPI**, para construir servicios de alto rendimiento que conecten los componentes del sistema.
- **Base de Datos**: **PostgreSQL** con la extensión **PostGIS**, para el manejo nativo de datos geoespaciales y cálculos de distancia.

## 3. Componentes de Agente de la IA "Claude"

### 3.1. Agente de Orquestación (workflow-orchestrator)
- **Responsabilidad**: Dirigir el flujo de trabajo, coordinando la ejecución de los demás agentes en la secuencia correcta.
- **Función Clave**: Activar agentes específicos basado en el estado de un pedido (e.g., llamar al Agente de Ruteo cuando un pedido está "Documentado"). Generar reportes de cumplimiento.

### 3.2. Agente de Arquitectura de Datos (data-architecture-validator)
- **Responsabilidad**: Garantizar la integridad, escalabilidad y correcta relación de los modelos de datos.
- **Función Clave**: Validar que el esquema de la base de datos (relación Pedidos-Facturas, Usuarios-Pedidos) soporte las consultas de negocio y el crecimiento a futuro.

### 3.3. Agente de Product Management  (business-policy-architect)
- **Responsabilidad**: Ser el custodio de las políticas de negocio dentro del sistema.
- **Función Clave**: Traducir requerimientos funcionales en lógica aplicable. Por ejemplo, implementar la regla que prohíbe entregas "mismo día" para pedidos ingresados después de las 3:00 PM. Definir las políticas de acceso y permisos.

### 3.4. Agente de Desarrollo de Lógica de Negocio (business-logic-developer)
- **Responsabilidad**: Implementar las funcionalidades técnicas y conexiones del sistema.
- **Función Clave**: Crear los servicios, hooks y lógica de negocio (ej. cambio de estados), conectar con APIs externas (mapas) y desarrollar interfaces internas como el "Mantenedor de Usuarios".

### 3.5. Agente de Logística y Ruteo, Optimization Engine (route-optimizer)
- **Responsabilidad**: Resolver el problema de optimización de rutas (Traveling Salesperson Problem - TSP).
- **Función Clave**: Analizar el tráfico, la geografía local y las restricciones de entrega para generar la secuencia de paradas más eficiente.

### 3.6. Agente de Geocodificación y Datos Maestros (geocoding-data-validator)
- **Responsabilidad**: Asegurar la calidad y precisión de los datos de dirección.
- **Función Clave**: Convertir direcciones textuales ("Cerca del estadio") en coordenadas geográficas precisas (Lat, Long) o rechazarlas si son insuficientes, para no comprometer al motor de ruteo.

### 3.7. Agente de Notificaciones y Experiencia de Cliente UX (customer-notification-ux)
- **Responsabilidad**: Gestionar la comunicación saliente hacia el cliente final.
- **Función Clave**: Disparar notificaciones (vía WhatsApp, Email, etc.) cuando un pedido cambia a estado "En Ruta", informando al cliente proactivamente.

### 3.8. Agente de Quality Assurance (QA) (qa-security-tester)
- **Responsabilidad**: Identificar fallos, inconsistencias y vulnerabilidades en la lógica del sistema.
- **Función Clave**: Diseñar y ejecutar pruebas de estrés, lógicas y de seguridad. Por ejemplo: verificar que un pedido a las 15:01 no se asigne a "mismo día" o que un rol de "Repartidor" no pueda acceder a funciones de administrador.

### 3.9. Agente de DevOps (devops-infrastructure-manager) 
- **Responsabilidad**: Gestionar la infraestructura y el despliegue del sistema Claude.
- **Función Clave**: Configurar el entorno de ejecución (e.g., Supabase, AWS) y administrar el acceso seguro a recursos y APIs.

## 4. Requerimientos Funcionales Clave

### 4.1. Gestión de Horarios de Corte (Cut-off)
- **Regla AM**: Pedidos hasta las 12:00 PM $\rightarrow$ elegibles para "Entrega Mismo Día".
- **Regla PM**: Pedidos después de las 3:00 PM $\rightarrow$ "Entrega Día Siguiente".
- **Control**: El sistema debe impedir que los vendedores fuercen la entrega "mismo día" fuera de horario, a menos que un `Administrador` lo autorice explícitamente, dejando un registro de auditoría.

### 4.2. Gestión de Facturación y Estados de Pedido
- **Validación Crítica**: Ningún pedido puede ser incluido en una ruta de despacho sin tener una factura/boleta asociada.
- **Disparador de Estado**: Al vincularse el documento fiscal, el estado del pedido debe cambiar de "En Preparación" a "Documentado", habilitándolo para el Agente de Ruteo.

### 4.3. Algoritmo de Optimización de Rutas
- **Entradas**: Coordenadas de entrega, capacidad del vehículo, ventanas horarias, datos de tráfico en tiempo real o histórico.
- **Salida**: Una secuencia ordenada de entregas que minimice la distancia total o el tiempo de viaje para un vehículo.
- **Contexto Geográfico**: El algoritmo debe estar parametrizado para la geografía de Rancagua y sus alrededores (Machalí, zonas periféricas).

### 4.4. Gestión de Perfiles y Seguridad
- El sistema debe implementar un Mantenedor de Usuarios con los siguientes campos por entidad:
    - `ID / UUID`: Identificador único.
    - `Username / Email`: Credencial de acceso.
    - `Password Hash`: Almacenamiento seguro (ej. Argon2, BCrypt).
    - `Role_ID`: Clave foránea a la tabla de roles/perfiles.
    - `Active_Status`: Booleano para activar/desactivar usuarios.

### 4.5. Auditoría y Trazabilidad (Audit Logs)
- El sistema debe registrar todas las acciones críticas, especialmente aquellas que intentan saltarse una regla de negocio.
- **Ejemplo de Log**: `[Timestamp] | Acción: "Cambio de fecha de entrega" | Usuario: "Vendedor_01" | Detalle: "Intento de forzar entrega hoy para pedido #123 (16:00)" | Resultado: "DENEGADO"`

## 5. Modelo de Datos y Entidades

- **Pedidos (Orders)**: Debe contener `timestamp` de compra, dirección, cliente y estado.
- **Facturas (Invoices)**: Contiene el número de documento fiscal y una relación directa con un `Pedido`.
- **Rutas (Routes)**: Almacena las rutas generadas, el orden de las paradas, y los tiempos estimados vs. reales para futuro re-entrenamiento del modelo.
- **Usuarios (Users)**: Ver especificación en la sección 4.4.

## 6. Ciclo de Vida del Pedido (Workflow)
1.  **Pendiente**: Pedido recién ingresado.
2.  **En Preparación**: Pedido siendo preparado en bodega (picking).
3.  **Documentado**: Se ha vinculado la factura. Es el paso crítico que lo habilita para despacho.
4.  **En Ruta**: Asignado a un vehículo que ha salido de bodega.
5.  **Entregado**: El repartidor confirma la entrega.
6.  **Incidencia**: La entrega no pudo ser completada.

## 7. Apéndice: Perfiles de Usuario del Sistema

- **Encargado de Bodega (Administrador de Ruta)**: Supervisa el proceso, valida la documentación y autoriza la generación de rutas propuestas por Claude.
- **Vendedores**: Ingresan pedidos y están sujetos a las reglas de negocio impuestas por Claude.
- **Repartidores**: Consumen la ruta generada por Claude a través de una interfaz móvil y actualizan el estado de las entregas.


## 8. Skill de la IA "Claude"
Considerar el uso de las siguientes Skill de Claude para el desarrollo:

 agent-development
 frontend-design
 mcp-integration
 senior-backend
 senior-architect
 skill-development


