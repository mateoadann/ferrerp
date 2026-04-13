# Changelog

Todos los cambios notables del proyecto FerrERP se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

---

## [Unreleased] — En desarrollo (dev)

### Nuevas funcionalidades
- Mejoras UX y fix de paginación HTMX en staging (#49)
- Autocomplete de clientes con navegación por teclado (#46)
- Logo de empresa en documentos PDF (#44)
- Actualización masiva de precios por categoría (#43)
- Dividir pagos en ventas, descuentos unitarios por producto y descuento inverso con monto exacto (#42)

### Mejoras
- Optimización de queries y refuerzo de seguridad multi-tenant (#45)
- Validaciones de seguridad adicionales y correcciones de QA (#44)
- Números de venta y presupuesto como links con color por estado (#42)
- Auto-dismiss de alertas flash a los 10 segundos (#42)
- Favicon en páginas de auth (#42)
- Ajuste de layout POS para nueva columna de descuento (#42)

### Correcciones
- Conversión segura de Decimal en POS para evitar ConversionSyntax (#48)
- Anulación de ventas crea egresos en caja y agrupamiento correcto (#42)
- Validación de pago dividido en modal de conversión y POS (#42)
- Ordenamiento cronológico de ventas en seed (#42)

### Migraciones
- Nueva columna de descuento en items de venta
- Campo `logo` en modelo Empresa
- Campo `porcentaje_aumento` para actualización masiva de precios

---

## [1.5.0] — 2026-03-26

### Nuevas funcionalidades
- Usuario superadmin con panel de administración de tenants (#25)
- Comando `make crear-superadmin` para crear superadmin por CLI (#25)
- Decoradores `superadmin_required` y `empresa_aprobada_required` (#25)
- Redirección por rol en login y cambio obligatorio de contraseña (#25)
- Mejoras de clientes: link venta en cuenta corriente y cumpleaños (#31)
- Opción de remito sin precios para ventas a cuenta corriente (#31)
- Renombrar PDF de ventas a "Remito" y botón "Descargar Presupuesto" (#31)

### Mejoras
- Sidebar propio para superadmin con banner de empresa pendiente (#25)
- Layout PDF compacto para presupuestos (#31)
- Ocultamiento de tickets en UI de ventas (#31)

### Correcciones
- Guardar `fecha_nacimiento` al crear y editar clientes (#33, #34)
- Ajustar context processor y dashboard para superadmin sin empresa (#25)
- Actualizar fixture empresa con `aprobada=True` para tests existentes (#25)

### Seguridad
- Aplicar `empresa_aprobada_required` a rutas de escritura de negocio (#25)

### Migraciones
- Nuevo rol `superadmin` en enum de usuarios
- Campo `aprobada` en modelo Empresa
- Campo `debe_cambiar_password` en modelo Usuario

---

## [1.4.0] — 2026-03-04

### Nuevas funcionalidades
- Zona horaria Argentina (UTC-3) en lugar de UTC (#18)
- Forma de pago QR en ventas, caja y formularios (#21)
- Edición y eliminación de categorías con tabla compacta y collapse (#20)
- Mejorar video demo con datos realistas en la landing (#23)

### Mejoras
- Color único para cada forma de pago en historial de ventas (#21)
- Formateo consistente de stock según unidad de medida (#19)
- Hint de separador decimal en campos de stock y cantidad (#19)
- Mejorar imagen del dashboard en la landing (#23)

### Correcciones
- Corregir campo cantidad en ajuste de stock y flash messages (#19)
- Corregir decimales excesivos en campos Stock Actual y Stock Mínimo (#19)
- Usar filtro `|stock` en cantidades de ventas, presupuestos, compras y PDFs (#19)

### Documentación
- Actualizar README con enlace a ferrerp.app (#22)

### Tests
- Tests de validación decimal en formularios de productos (#19)

---

## [1.3.0] — 2026-03-04

### Nuevas funcionalidades
- Eliminar rol owner y simplificar a `administrador` / `vendedor` (#16)
- Permitir a vendedores gestionar categorías desde Configuración (#16)

### Seguridad
- Proteger mínimo 1 administrador activo por empresa (#16)

### Migraciones
- Eliminación del rol `owner` del enum de roles de usuario

---

## [1.2.0] — 2026-03-03

### Nuevas funcionalidades
- Migrar dominios a ferrerp.app y panel.ferrerp.app (#14)

---

## [1.1.0] — 2026-03-03

### Mantenimiento
- Agregar `node_modules/` y `out/` a `.gitignore` (#12)
- Incluir `package-lock.json` de Remotion en el repositorio (#12)

---

## [1.0.0] — 2026-03-03

Release inicial con todas las funcionalidades base del sistema.

### Nuevas funcionalidades
- Landing page con configuración nginx y deploy con SSL (#9)
- Separar POS y Ventas en el sidebar (#8)
- Mejoras UI, placeholder de facturación y órdenes sin precio (#7)
- IVA por producto con discriminación en ventas y presupuestos (#2)
- Modelo Empresa y fundación multi-tenant (#3)
- `empresa_id` en modelos core con categorías jerárquicas (#4)
- `empresa_id` en modelos transaccionales con filtrado en rutas (#5)
- Protección de ramas con hooks locales y rulesets de GitHub (#1)

### Mejoras
- Rediseñar modal IVA con comparación lado a lado (#7)
- Defensa en profundidad en queries de registros hijo con `query_empresa()` (#6)

### Correcciones
- Corregir entrypoint de Remotion y replicar UI real en escenas (#10)
- Usar Material Symbols y reducir video a 38 segundos (#10)
- Manejar `current_user None` en `Configuracion.get()`/`set()` (#5)

### Base del proyecto (pre-PRs)
- Módulo de compras y reportes
- Caja y cuenta corriente
- Punto de venta (POS) con formato monetario
- Presupuestos con servicio y tests
- Tests unitarios de modelos
- Configuración de pytest, ruff y CI con GitHub Actions
- Docker Compose para desarrollo
