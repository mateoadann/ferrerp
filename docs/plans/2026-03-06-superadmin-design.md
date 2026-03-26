# Diseño: Superadmin para FerrERP

Fecha: 2026-03-06

## Resumen

Implementar un usuario "superadmin" unico en la base de datos, creado via comando CLI,
que puede gestionar todos los tenants (empresas) de la aplicacion. Este usuario no pertenece
a ninguna empresa y tiene su propio layout con dashboard y gestion de empresas.

## 1. Modelo de datos

### Cambios en Usuario

- Nuevo valor de rol: `superadmin` (ademas de `administrador` y `vendedor`)
- `empresa_id` pasa a ser **nullable** (el superadmin no pertenece a ninguna empresa)
- Nuevo campo `debe_cambiar_password` (Boolean, default=False) para forzar cambio tras reset
- Restriccion: solo puede existir UN usuario con rol `superadmin` en toda la BD

### Cambios en Empresa

- Nuevo campo `aprobada` (Boolean, default=False) para controlar si el tenant puede operar
- Las empresas existentes deben migrar con `aprobada=True`

## 2. Comando CLI

```bash
flask crear-superadmin --email X --nombre Y --password Z
```

- Valida que no exista ya un superadmin
- Crea usuario con rol `superadmin`, `empresa_id=None`, `activo=True`
- Si ya existe, muestra error

## 3. Autenticacion y acceso

### Login

- El superadmin usa el mismo `/auth/login`
- Tras autenticarse: si `rol == superadmin` redirige a `/superadmin/dashboard`
- Verificacion de `debe_cambiar_password=True` redirige a formulario de cambio obligatorio

### Decoradores nuevos

- `@superadmin_required`: verifica que el usuario sea superadmin
- `@empresa_aprobada_required`: bloquea escrituras si `empresa.aprobada == False`

### Proteccion multi-tenant

El superadmin (empresa_id=None) solo accede a rutas bajo `/superadmin/`.
Las queries multi-tenant existentes no se ven afectadas.

## 4. Flujo de aprobacion de tenants

1. Usuario se registra normalmente -> Empresa con `aprobada=False`
2. El usuario puede hacer login y navegar en **modo read-only**
3. El superadmin ve la empresa como "Pendiente" en su listado
4. El superadmin aprueba -> `empresa.aprobada = True`
5. El usuario puede operar normalmente

### Modo read-only

- Decorador `@empresa_aprobada_required` en rutas de escritura
- Banner persistente: "Tu empresa esta pendiente de aprobacion"
- Rutas de solo lectura (listar, ver dashboard) siguen accesibles

## 5. Blueprint y rutas del superadmin

Blueprint: `superadmin` con prefix `/superadmin/`

| Ruta | Metodo | Funcion |
|------|--------|---------|
| `/superadmin/` | GET | Dashboard con metricas |
| `/superadmin/empresas` | GET | Listado de empresas (filtro por estado) |
| `/superadmin/empresas/<id>/aprobar` | POST | Aprobar empresa |
| `/superadmin/empresas/<id>/desactivar-admin` | POST | Desactivar usuario admin |
| `/superadmin/empresas/<id>/activar-admin` | POST | Reactivar usuario admin |
| `/superadmin/empresas/<id>/reset-password` | POST | Generar contrasena temporal |

## 6. Layout del superadmin

Sidebar propio con 2 items:
- Dashboard (metricas: total empresas, pendientes, activas, inactivas)
- Empresas (listado con acciones)

No comparte el sidebar de los tenants.
Se decide que sidebar mostrar segun `current_user.rol == 'superadmin'`.

## 7. Reset de contrasena

1. Superadmin hace clic en "Reset Password" en un admin
2. Se genera contrasena aleatoria (12 caracteres, alfanumerica)
3. Se hashea y guarda, se marca `debe_cambiar_password=True`
4. Se muestra la contrasena en un modal para que el superadmin la copie
5. Cuando el admin hace login, detecta `debe_cambiar_password=True` -> redirige a cambio obligatorio
6. Tras cambiar, `debe_cambiar_password=False`

## 8. Impacto en codigo existente

- `empresa_id` nullable en modelo Usuario -> migracion
- `aprobada` en modelo Empresa -> migracion (default True para existentes)
- Registro (`auth.py`) -> crear empresa con `aprobada=False`
- Sidebar (`sidebar.html`) -> condicional: superadmin muestra sidebar propio
- Base template -> banner de "pendiente aprobacion" si `empresa.aprobada == False`
- Decoradores -> agregar `@superadmin_required` y `@empresa_aprobada_required`
- Login -> redirigir segun rol; verificar `debe_cambiar_password`
- Queries multi-tenant -> superadmin no usa empresa_id, solo accede a rutas propias
