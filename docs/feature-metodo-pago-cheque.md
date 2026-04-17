# Feature: Nuevo Metodo de Pago — Cheque

## Resumen ejecutivo

Esta feature agrega **cheque** como nueva forma de pago en FerrERP. Cuando el ferretero cobra una venta con cheque, el sistema registra los datos del cheque (numero, banco, fecha de vencimiento e importe) junto con la venta. Aplica tanto al punto de venta (POS) como al cobro de cuenta corriente y al pago dividido.

El cheque se trata como un pago **no liquido**: ingresa a caja como movimiento registrado, pero no suma al efectivo fisico. Esto permite al ferretero tener trazabilidad completa de los cheques recibidos sin distorsionar el arqueo de caja.

---

## Contexto y problema de negocio

### La realidad del cheque en la ferreteria

En Argentina, el cheque sigue siendo un medio de pago habitual para compras de montos medianos/altos, especialmente entre clientes que son empresas constructoras, electricistas, plomeros u otros comercios. El ferretero recibe el cheque, lo guarda, y lo deposita cuando llega la fecha de vencimiento.

El flujo actual en FerrERP NO soporta cheques. Cuando un cliente paga con cheque, el ferretero tiene que:

1. Registrar la venta como "efectivo" o "transferencia" (mentira contable)
2. Anotar en un cuaderno los datos del cheque por separado
3. Recordar cuando vence para depositarlo
4. Si el cheque rebota, no tiene forma de vincular el rebote con la venta original

**El ferretero pierde trazabilidad.** No puede saber cuantos cheques tiene en cartera, cuales vencen esta semana, ni cuanto cobro con cheques en el mes.

### Ejemplo concreto

| Paso | Accion | Sin esta feature | Con esta feature |
|------|--------|------------------|------------------|
| 1 | Cliente compra $15.000 y paga con cheque | Registra como "efectivo" | Registra como "cheque" + datos del cheque |
| 2 | Ferretero quiere saber cuanto tiene en cheques | Busca en el cuaderno | Filtra por forma de pago "cheque" en historial |
| 3 | Cheque vence el viernes | Se acuerda si se acuerda | Puede consultar cheques por fecha de vencimiento |

---

## Analisis del codebase actual

### Lo que YA funciona sin cambios

Se verifico exhaustivamente contra el codigo:

| Componente | Estado | Evidencia |
|-----------|--------|-----------|
| `VentaPago` soporta multiples formas | OK | Modelo independiente en `venta_pago.py` |
| Pago dividido permite 2 formas | OK | `ventas.py:241` valida `len(pagos_data) == 2` |
| `MovimientoCaja` registra ingresos por venta | OK | `caja.py:104-148` |
| Ticket muestra forma de pago | OK | `ticket.html:250-270` |
| Precedente de agregar enum (`qr`) | OK | `migrations/versions/0005_agregar_forma_pago_qr.py` |
| Anulacion revierte por forma de pago | OK | `ventas.py:606-698` |

### Lo que BLOQUEA y requiere cambios

| Componente | Problema | Archivo:Linea |
|-----------|----------|---------------|
| Enum `forma_pago` (ventas) | No incluye `'cheque'` | `venta.py:26-29` |
| Enum `forma_pago` (VentaPago) | No incluye `'cheque'` | `venta_pago.py:22-27` |
| Enum `forma_pago_movimiento` (caja) | No incluye `'cheque'` | `caja.py:131-139` |
| `forma_pago_display` (Venta) | No mapea `'cheque'` | `venta.py:67-74` |
| `forma_pago_display` (VentaPago) | No mapea `'cheque'` | `venta_pago.py:44-51` |
| `forma_pago_display` (MovimientoCaja) | No mapea `'cheque'` | `caja.py:173-179` |
| Template POS | No tiene boton de cheque | `punto_venta.html:292-336` |
| Template POS dividido | No tiene opcion cheque en selects | `punto_venta.html:344-372` |
| Template CC pago | No tiene opcion cheque | `cuenta_corriente.html:331-347` |
| Template CC adelanto | No tiene opcion cheque | `cuenta_corriente.html:373-389` |
| Template ticket | No muestra "Cheque" | `ticket.html:265-270` |
| Modelo de datos cheque | No existe tabla para datos del cheque | -- |
| Ruta de venta | No captura datos de cheque | `ventas.py:60-510` |
| Ruta de pago CC | No captura datos de cheque | `clientes.py:221-332` |
| Anulacion | No revierte/invalida cheque | `ventas.py:580-698` |

---

## Requerimientos funcionales

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| CHQ-01 | Agregar `'cheque'` como valor valido en los enums `forma_pago` y `forma_pago_movimiento` | Alta |
| CHQ-02 | Crear modelo `Cheque` para almacenar datos del cheque (numero, banco, fecha vencimiento, importe) | Alta |
| CHQ-03 | Mostrar boton "Cheque" en la grilla de formas de pago del POS | Alta |
| CHQ-04 | Al seleccionar cheque en POS, mostrar formulario inline con campos del cheque | Alta |
| CHQ-05 | Permitir cheque como forma de pago en pago dividido | Alta |
| CHQ-06 | Registrar pago de cuenta corriente con cheque | Alta |
| CHQ-07 | Registrar adelanto con cheque | Alta |
| CHQ-08 | Mostrar datos del cheque en el ticket de venta | Media |
| CHQ-09 | Mostrar "Cheque" en el historial de ventas y detalle de venta | Alta |
| CHQ-10 | Al anular una venta pagada con cheque, marcar el cheque como anulado | Alta |
| CHQ-11 | Validar que todos los campos obligatorios del cheque esten completos al confirmar la venta | Alta |
| CHQ-12 | Validar que el importe del cheque coincida con el monto de la venta (o la porcion en pago dividido) | Alta |
| CHQ-13 | Permitir consultar cheques recibidos en una vista basica de listado | Baja |

---

## Modelo de datos

### Nuevo modelo: `Cheque`

```python
# app/models/cheque.py

class Cheque(EmpresaMixin, db.Model):
    """Modelo de cheque recibido como forma de pago."""

    __tablename__ = 'cheques'

    id = db.Column(db.Integer, primary_key=True)
    numero_cheque = db.Column(db.String(30), nullable=False)
    banco = db.Column(db.String(100), nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    importe = db.Column(db.Numeric(12, 2), nullable=False)

    # Vinculacion polimorfica (igual que MovimientoCaja.referencia_tipo/id)
    referencia_tipo = db.Column(db.String(30), nullable=False)
    # Valores: 'venta', 'pago_cc', 'adelanto'
    referencia_id = db.Column(db.Integer, nullable=False)

    estado = db.Column(
        db.Enum('activo', 'anulado', name='estado_cheque'),
        default='activo',
        nullable=False,
    )

    created_at = db.Column(db.DateTime, default=ahora_argentina)

    def __repr__(self):
        return f'<Cheque {self.numero_cheque} - {self.banco} ${self.importe}>'

    @property
    def estado_display(self):
        opciones = {
            'activo': 'Activo',
            'anulado': 'Anulado',
        }
        return opciones.get(self.estado, self.estado)

    @property
    def esta_vencido(self):
        from datetime import date
        return self.fecha_vencimiento < date.today()

    def to_dict(self):
        return {
            'id': self.id,
            'numero_cheque': self.numero_cheque,
            'banco': self.banco,
            'fecha_vencimiento': self.fecha_vencimiento.isoformat(),
            'importe': float(self.importe),
            'referencia_tipo': self.referencia_tipo,
            'referencia_id': self.referencia_id,
            'estado': self.estado,
            'estado_display': self.estado_display,
        }
```

### Justificacion del diseño

**Por que un modelo separado y no campos en `VentaPago`:**

- Un cheque puede venir de una venta directa, de un pago de cuenta corriente, o de un adelanto. Los tres flujos son distintos.
- La vinculacion polimorfica (`referencia_tipo` + `referencia_id`) sigue el patron ya establecido en `MovimientoCaja` (`caja.py:142-143`).
- Permite consultar todos los cheques en cartera con un simple query a la tabla `cheques`.
- No agrega columnas nulas a `VentaPago` (que no aplicarian para el 90% de los pagos).

**Por que NO un modelo `ChequeDetalle` separado de la venta:**

- El cheque es intrinsecamente un medio de pago. Su ciclo de vida esta atado a la transaccion que lo origino. Si se anula la venta, se anula el cheque.

### Cambios en enums existentes

#### Enum `forma_pago` (tabla `ventas` y `venta_pagos`)

```
Actual:  'efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia', 'qr', 'cuenta_corriente', 'dividido'
Nuevo:   'efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia', 'qr', 'cuenta_corriente', 'dividido', 'cheque'
```

#### Enum `forma_pago_movimiento` (tabla `movimientos_caja`)

```
Actual:  'efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia', 'qr'
Nuevo:   'efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia', 'qr', 'cheque'
```

---

## Migracion de base de datos

```python
# migrations/versions/0014_agregar_forma_pago_cheque.py

"""Agregar forma de pago cheque y tabla cheques.

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Agregar 'cheque' a los enums
    op.execute("ALTER TYPE forma_pago ADD VALUE IF NOT EXISTS 'cheque'")
    op.execute("ALTER TYPE forma_pago_movimiento ADD VALUE IF NOT EXISTS 'cheque'")

    # 2. Crear enum estado_cheque
    estado_cheque = sa.Enum('activo', 'anulado', name='estado_cheque')
    estado_cheque.create(op.get_bind(), checkfirst=True)

    # 3. Crear tabla cheques
    op.create_table(
        'cheques',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('numero_cheque', sa.String(30), nullable=False),
        sa.Column('banco', sa.String(100), nullable=False),
        sa.Column('fecha_vencimiento', sa.Date(), nullable=False),
        sa.Column('importe', sa.Numeric(12, 2), nullable=False),
        sa.Column('referencia_tipo', sa.String(30), nullable=False),
        sa.Column('referencia_id', sa.Integer(), nullable=False),
        sa.Column(
            'estado',
            sa.Enum('activo', 'anulado', name='estado_cheque', create_type=False),
            server_default='activo',
            nullable=False,
        ),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_cheques_empresa_id', 'cheques', ['empresa_id'])
    op.create_index('ix_cheques_fecha_vencimiento', 'cheques', ['fecha_vencimiento'])
    op.create_index('ix_cheques_referencia', 'cheques', ['referencia_tipo', 'referencia_id'])


def downgrade():
    op.drop_table('cheques')
    sa.Enum(name='estado_cheque').drop(op.get_bind(), checkfirst=True)
    # No se puede eliminar valor de enum en PostgreSQL
```

---

## Flujos de usuario

### Flujo 1: Venta directa con cheque en POS

1. El vendedor arma la venta normalmente (agrega productos, cliente opcional)
2. En la grilla de formas de pago, selecciona **Cheque**
3. Se despliega un formulario inline debajo de la grilla con:
   - Numero de cheque (texto, obligatorio)
   - Banco (texto, obligatorio)
   - Fecha de vencimiento (date picker, obligatorio)
   - Importe (numerico, pre-llenado con el total de la venta, obligatorio)
4. El vendedor completa los datos y confirma la venta
5. El sistema:
   - Crea la `Venta` con `forma_pago='cheque'`
   - Crea un `VentaPago` con `forma_pago='cheque'`
   - Crea un `MovimientoCaja` con `forma_pago='cheque'`
   - Crea un registro `Cheque` con `referencia_tipo='venta'` y `referencia_id=venta.id`
   - Descuenta stock normalmente

### Flujo 2: Pago dividido con cheque

1. El vendedor selecciona "Dividido"
2. En uno de los dos selectores de forma de pago, elige "Cheque"
3. Al elegir cheque en el selector, se despliegan los campos del cheque debajo de ese selector
4. El vendedor completa montos y datos del cheque
5. El sistema:
   - Crea la `Venta` con `forma_pago='dividido'`
   - Crea dos `VentaPago`, uno con `forma_pago='cheque'`
   - Crea `MovimientoCaja` para cada pago
   - Crea un registro `Cheque` vinculado a la venta

### Flujo 3: Cobro de cuenta corriente con cheque

1. En la pantalla de cuenta corriente del cliente, el ferretero va a registrar pago
2. En el modal de seleccion de forma de pago, aparece la opcion **Cheque**
3. Al seleccionar cheque, se muestran los campos del cheque dentro del modal
4. El ferretero completa monto del pago + datos del cheque y confirma
5. El sistema:
   - Actualiza saldo de CC del cliente
   - Crea `MovimientoCuentaCorriente` tipo pago
   - Crea `MovimientoCaja` con `forma_pago='cheque'`
   - Crea un registro `Cheque` con `referencia_tipo='pago_cc'`

### Flujo 4: Adelanto con cheque

Identico al flujo 3, pero con `referencia_tipo='adelanto'`.

### Flujo 5: Anulacion de venta con cheque

1. Al anular una venta pagada con cheque, el sistema:
   - Revierte stock (sin cambios al flujo actual)
   - Crea egreso en caja con `forma_pago='cheque'`
   - Marca el registro `Cheque` asociado como `estado='anulado'`
2. Si era pago dividido con un componente cheque, solo se anula ese cheque

---

## Cambios en UI

### POS — Boton de cheque en grilla

Se agrega un boton mas a la grilla de formas de pago (`punto_venta.html:292-336`), entre QR y Cta. Cte.:

```html
<div class="payment-method"
     :class="{'active': formaPago === 'cheque'}"
     @click="formaPago = 'cheque'">
    <span class="material-symbols-rounded d-block mb-1">description</span>
    <small>Cheque</small>
</div>
```

Icono sugerido: `description` (Material Symbols Rounded) — representa un documento.

### POS — Formulario inline de datos del cheque

Se muestra condicionalmente cuando `formaPago === 'cheque'` (o cuando un selector de pago dividido tiene cheque):

```html
<div x-show="formaPago === 'cheque'" x-cloak>
    <div class="row g-2 mt-2">
        <div class="col-6">
            <label class="form-label small text-muted">Numero de cheque</label>
            <input type="text" class="form-control form-control-sm"
                   name="cheque_numero" x-model="chequeNumero" required>
        </div>
        <div class="col-6">
            <label class="form-label small text-muted">Banco</label>
            <input type="text" class="form-control form-control-sm"
                   name="cheque_banco" x-model="chequeBanco" required>
        </div>
        <div class="col-6">
            <label class="form-label small text-muted">Fecha de vencimiento</label>
            <input type="date" class="form-control form-control-sm"
                   name="cheque_fecha_vencimiento" x-model="chequeFechaVencimiento" required>
        </div>
        <div class="col-6">
            <label class="form-label small text-muted">Importe</label>
            <div class="input-group input-group-sm">
                <span class="input-group-text">$</span>
                <input type="number" class="form-control"
                       name="cheque_importe" x-model="chequeImporte"
                       step="0.01" min="0.01" required>
            </div>
        </div>
    </div>
</div>
```

### POS — Selectores de pago dividido

Se agrega `<option value="cheque">Cheque</option>` a los dos `<select>` de pago dividido (`punto_venta.html:344-372`).

Cuando un selector tiene valor `'cheque'`, se muestran los campos del cheque debajo de ese selector.

### Cuenta corriente — Modal de forma de pago

Se agrega un boton mas en ambos modales (pago y adelanto) en `cuenta_corriente.html`:

```html
<div class="payment-method" data-value="cheque">
    <span class="material-symbols-rounded d-block mb-1">description</span>
    <small>Cheque</small>
</div>
```

Al seleccionar cheque, se muestran los campos del cheque dentro del modal, debajo de los botones de forma de pago.

### Ticket de venta

En `ticket.html` se agrega el caso para cheque:

```
{% elif venta.forma_pago == 'cheque' %}Cheque
```

Y opcionalmente, debajo de la forma de pago, mostrar datos del cheque:

```
Cheque Nro: 12345678 - Banco Nacion
Vto: 20/05/2026
```

---

## Validaciones

| Validacion | Donde aplica | Regla |
|------------|-------------|-------|
| Numero de cheque obligatorio | POS, CC pago, CC adelanto | No puede estar vacio |
| Banco obligatorio | POS, CC pago, CC adelanto | No puede estar vacio |
| Fecha de vencimiento obligatoria | POS, CC pago, CC adelanto | No puede estar vacia |
| Fecha de vencimiento no pasada | POS, CC pago, CC adelanto | Debe ser >= hoy (configurable, ver edge cases) |
| Importe > 0 | POS, CC pago, CC adelanto | Debe ser mayor a cero |
| Importe = total de venta | POS (pago simple) | El importe del cheque debe coincidir con el total |
| Importe = porcion del pago | POS (pago dividido) | El importe del cheque debe coincidir con el monto asignado a cheque |
| Numero de cheque: formato libre | Todos | Se permite alfanumerico, no se valida formato (cada banco tiene el suyo) |

---

## Edge cases

| Caso | Comportamiento esperado |
|------|------------------------|
| Cheque con fecha de vencimiento pasada | Rechazar con mensaje: "La fecha de vencimiento del cheque no puede ser anterior a hoy". Nota: en una fase futura se podria hacer configurable para aceptar cheques ya vencidos que el cliente trae atrasados |
| Pago dividido con los dos metodos como cheque | Rechazar: "Las formas de pago deben ser distintas" (validacion existente en `ventas.py:247`) |
| Anulacion de venta con cheque ya depositado | Fuera de alcance de esta feature. El sistema marca el cheque como `anulado` pero no modela el deposito bancario. Se puede agregar en una futura feature de gestion de cheques en cartera |
| Cheque con importe distinto al total | Rechazar con mensaje: "El importe del cheque debe coincidir con el monto del pago" |
| Pago de CC con cheque por monto mayor a la deuda | Rechazar (validacion existente en `clientes.py:253`) |
| Devolucion parcial de venta pagada con cheque | Fuera de alcance. Las devoluciones parciales no modifican la forma de pago original |
| Cierre de caja con cheques | Los cheques NO suman al efectivo esperado en caja. El `calcular_monto_esperado()` en `caja.py:63-66` ya filtra por `forma_pago == 'efectivo'`, asi que el cheque queda excluido automaticamente |

---

## Cambios tecnicos necesarios

### Archivos nuevos

| Archivo | Descripcion |
|---------|-------------|
| `app/models/cheque.py` | Modelo `Cheque` |
| `migrations/versions/0014_agregar_forma_pago_cheque.py` | Migracion: enum + tabla |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `app/models/__init__.py` | Importar y exportar `Cheque` |
| `app/models/venta.py` | Agregar `'cheque'` al enum `forma_pago` (linea 26-29) y al dict `forma_pago_display` (linea 67-74) |
| `app/models/venta_pago.py` | Agregar `'cheque'` al enum (linea 22-27) y al dict display (linea 44-51) |
| `app/models/caja.py` | Agregar `'cheque'` al enum `forma_pago_movimiento` (linea 131-139) y al dict display (linea 173-179) |
| `app/routes/ventas.py` | Capturar datos de cheque en POST, crear registro `Cheque`, manejar en anulacion |
| `app/routes/clientes.py` | Capturar datos de cheque en `registrar_pago` y `registrar_adelanto` |
| `app/templates/ventas/punto_venta.html` | Boton cheque, formulario inline, opciones en selects de dividido, variables Alpine.js |
| `app/templates/ventas/ticket.html` | Mostrar "Cheque" y datos del cheque |
| `app/templates/clientes/cuenta_corriente.html` | Opcion cheque en modales de pago y adelanto, campos del cheque |

### Archivos que NO necesitan cambios

| Archivo | Razon |
|---------|-------|
| `app/models/caja.py` (calculo de caja) | `calcular_monto_esperado()` filtra por `efectivo`, cheques quedan excluidos |
| `app/models/cliente.py` | La logica de CC no depende de la forma de pago |
| `app/models/cuenta_corriente.py` | MovimientoCuentaCorriente no tiene forma de pago |
| `app/services/` | No hay servicio de ventas; la logica esta en las rutas |
| `tests/conftest.py` | No requiere fixture nueva (los tests crean sus datos) |

---

## Fases de implementacion

### Fase 1: Backend — Modelo y migracion

1. Crear `app/models/cheque.py` con el modelo `Cheque`
2. Actualizar `app/models/__init__.py`
3. Crear migracion `0014_agregar_forma_pago_cheque.py`
4. Agregar `'cheque'` a los enums en los modelos `Venta`, `VentaPago`, `MovimientoCaja`
5. Agregar `'Cheque'` a los dicts `forma_pago_display` en los tres modelos

### Fase 2: Backend — Logica de venta con cheque

1. Modificar `app/routes/ventas.py`:
   - En el POST de `punto_de_venta`: capturar campos `cheque_*` del form
   - Crear registro `Cheque` al registrar venta con cheque
   - Manejar cheque en pago dividido
   - En `anular_venta`: marcar cheque como anulado
2. Validaciones server-side de datos del cheque

### Fase 3: Backend — Cheque en cuenta corriente

1. Modificar `app/routes/clientes.py`:
   - En `registrar_pago`: capturar datos de cheque, crear registro
   - En `registrar_adelanto`: capturar datos de cheque, crear registro
2. Validaciones server-side

### Fase 4: Frontend — POS

1. Agregar boton cheque a la grilla de formas de pago
2. Agregar formulario inline con campos del cheque (Alpine.js)
3. Agregar opcion cheque a los selects de pago dividido
4. Agregar variables Alpine.js: `chequeNumero`, `chequeBanco`, `chequeFechaVencimiento`, `chequeImporte`
5. Agregar hidden inputs para enviar datos del cheque en el form
6. Validacion client-side: campos obligatorios cuando `formaPago === 'cheque'`

### Fase 5: Frontend — Cuenta corriente y ticket

1. Agregar opcion cheque en modales de pago y adelanto
2. Campos del cheque en modales (JS vanilla, mismo patron que el existente)
3. Hidden inputs para enviar datos del cheque
4. Actualizar ticket para mostrar datos del cheque

### Fase 6: Tests

1. Test de creacion de venta con cheque
2. Test de pago dividido con cheque
3. Test de anulacion de venta con cheque (verificar cheque queda anulado)
4. Test de pago de CC con cheque
5. Test de adelanto con cheque
6. Test de validaciones (cheque sin numero, sin banco, fecha pasada, importe no coincide)

---

## Validacion contra el codebase

Se verifico cada afirmacion tecnica de este documento:

- **Enum `forma_pago` en `venta.py:26-29`**: confirmado, no incluye `'cheque'`
- **Enum `forma_pago` en `venta_pago.py:22-27`**: confirmado, usa `create_type=False` (comparte el tipo)
- **Enum `forma_pago_movimiento` en `caja.py:131-139`**: confirmado, tipo separado para movimientos de caja
- **`calcular_monto_esperado()` en `caja.py:63-66`**: confirmado, filtra `forma_pago == 'efectivo'`
- **Precedente de agregar enum en `0005_agregar_forma_pago_qr.py`**: confirmado, usa `ALTER TYPE ADD VALUE`
- **Pago dividido valida formas distintas en `ventas.py:247`**: confirmado
- **Vinculacion polimorfica en `caja.py:142-143`**: confirmado, `referencia_tipo` + `referencia_id`
- **Template POS grilla en `punto_venta.html:292-336`**: confirmado, 7 botones actuales
- **Template CC modales en `cuenta_corriente.html:331-389`**: confirmado, 5 opciones de pago
- **Anulacion en `ventas.py:606-698`**: confirmado, revierte por forma de pago
- **Ultima migracion `0013`**: confirmado via `migrations/versions/`
