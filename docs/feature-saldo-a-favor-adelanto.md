# Feature: Saldo a Favor / Adelanto de Cliente

## Resumen ejecutivo

Esta feature permite que un cliente entregue dinero por adelantado al ferretero, generando un **saldo a favor** en su cuenta corriente. Ese saldo puede luego consumirse total o parcialmente al realizar una compra por cuenta corriente.

Resuelve el caso de uso donde el cliente Juan le entrega $1.000 al ferretero como adelanto, ese monto queda como crédito en su cuenta corriente, y cuando Juan compra puede elegir cuánto de ese saldo usar para pagar.

---

## Contexto y problema de negocio

### Situación actual

El sistema de cuenta corriente de FerrERP permite:
- Vender a crédito (genera cargo en la CC del cliente)
- Registrar pagos del cliente (reduce deuda)
- Ver historial de movimientos

Pero **NO permite**:
- Recibir dinero anticipado de un cliente
- Que un cliente tenga saldo a favor (crédito positivo)
- Consumir ese saldo en una venta futura

### El caso de uso real

En las ferreterías es común que un cliente de confianza deje dinero "a cuenta" para futuras compras. Hoy el ferretero no tiene forma de registrar eso en el sistema, lo anota en un papelito o lo recuerda de memoria. Esto genera:

- Riesgo de olvidar el adelanto
- Discusiones sobre montos
- Falta de trazabilidad

---

## Análisis del codebase actual

### Lo que YA funciona sin cambios

Se verificó exhaustivamente contra el código:

| Componente | Estado | Evidencia |
|-----------|--------|-----------|
| `saldo_cuenta_corriente` puede ir negativo | ✅ Funciona | `Numeric(12,2)` sin CHECK constraint (`cliente.py:23`) |
| `actualizar_saldo()` no valida límites | ✅ Funciona | Suma/resta directa sin validar (`cliente.py:71-90`) |
| `puede_comprar_a_credito()` con saldo negativo | ✅ Funciona | Math: `-300 + 500 = 200 <= 1000` ✓ (`cliente.py:57-69`) |
| `credito_disponible` con saldo negativo | ✅ Funciona | `1000 - (-300) = 1300` ✓ (`cliente.py:41-44`) |
| `referencia_tipo` String(20) | ✅ Cabe | 'consumo_saldo_favor' = 19 chars (`cuenta_corriente.py:28`) |
| ALTER TYPE enum PostgreSQL | ✅ Precedente | Migración `0005_agregar_forma_pago_qr.py` |

### Lo que BLOQUEA y requiere cambios

| Componente | Problema | Archivo:Línea |
|-----------|----------|---------------|
| Validación de pago | `monto > saldo` bloquea sobrepago | `clientes.py:196` |
| Template CC | Formulario oculto si no tiene deuda | `cuenta_corriente.html:37` |
| Enum MovimientoCaja | No existe `'adelanto_cliente'` | `caja.py:140-146` |
| Reporte deudores | Solo muestra `saldo > 0` | `clientes.py:257` |
| POS | No muestra saldo a favor ni permite consumirlo | `ventas.py`, `punto_venta.html` |

---

## Cambios propuestos

### Cambio 1: Nueva ruta — Registrar Adelanto

**Archivo**: `app/routes/clientes.py`
**Ruta**: `POST /clientes/<id>/registrar-adelanto`
**Decoradores**: `@login_required`, `@empresa_aprobada_required`, `@caja_abierta_required`

**Flujo**:
1. Validar formulario (monto, forma_pago, motivo)
2. Obtener caja abierta del usuario
3. `cliente.actualizar_saldo(monto, 'pago')` → saldo puede quedar negativo
4. Crear `MovimientoCuentaCorriente`:
   - tipo=`'pago'`
   - referencia_tipo=`'adelanto'`
   - descripcion= motivo del usuario o "Adelanto de cliente"
5. Crear `MovimientoCaja`:
   - tipo=`'ingreso'`
   - concepto=`'adelanto_cliente'`
   - forma_pago= la que eligió el usuario

**Ejemplo**: Cliente tiene deuda de $500, entrega $800
- `actualizar_saldo(800, 'pago')` → saldo pasa de +500 a -300
- El cliente queda con $300 de saldo a favor

---

### Cambio 2: Anulación de adelanto

**Archivo**: `app/routes/clientes.py`
**Ruta**: `POST /clientes/<id>/anular-adelanto/<int:movimiento_id>`
**Decoradores**: `@login_required`, `@empresa_aprobada_required`, `@admin_required`, `@caja_abierta_required`

**Flujo**:
1. Obtener MovimientoCuentaCorriente por id, validar `referencia_tipo='adelanto'`
2. Validar que no se haya anulado ya (buscar movimiento con `referencia_tipo='anulacion_adelanto'` y `referencia_id=movimiento_id`)
3. `cliente.actualizar_saldo(movimiento.monto, 'cargo')` → revierte el saldo
4. Crear `MovimientoCuentaCorriente`:
   - tipo=`'cargo'`
   - referencia_tipo=`'anulacion_adelanto'`
   - referencia_id= id del movimiento original
5. Crear `MovimientoCaja`:
   - tipo=`'egreso'`
   - concepto=`'adelanto_cliente'`
   - descripcion= "Anulación de adelanto #X"

**Restricción**: Solo `@admin_required` puede anular adelantos.

---

### Cambio 3: Consumo de saldo a favor en ventas

**Archivos**: `app/routes/ventas.py`, `app/templates/ventas/punto_venta.html`

#### Condiciones para activar (las 3 deben cumplirse):
1. El cliente seleccionado tiene cuenta corriente (limite_credito > 0)
2. El cliente tiene saldo a favor (saldo_cuenta_corriente < 0)
3. La forma de pago elegida es `'cuenta_corriente'` (o la porción CC de `'dividido'`)

#### Flujo en el POS (frontend):
1. Usuario selecciona cliente → si tiene saldo a favor, mostrar badge: **"Saldo a favor: $X.XX"**
2. Usuario elige forma de pago `'cuenta_corriente'` (o dividido con porción CC)
3. Aparece sección condicional: "Este cliente tiene $X.XX de saldo a favor"
   - Input numérico: "Monto a consumir" (default: mínimo entre saldo a favor y monto CC de la venta)
   - Botón **"Todo"** que autocompleta con el saldo a favor disponible
4. Al confirmar la venta, el `monto_saldo_favor` se envía como parámetro adicional

#### Flujo en el backend (ventas.py):
1. Recibir `monto_saldo_favor` del request
2. Validar: `monto_saldo_favor <= abs(cliente.saldo_cuenta_corriente)`
3. Validar: `monto_saldo_favor <= monto_cc_de_la_venta`
4. El cargo neto a CC es: `monto_cc_de_la_venta - monto_saldo_favor`
5. Si `monto_saldo_favor > 0`:
   - Crear `MovimientoCuentaCorriente` tipo=`'cargo'`, referencia_tipo=`'consumo_saldo_favor'`, monto=monto_saldo_favor, referencia_id=venta.id
6. Si queda resto por cargar a CC (`monto_cc - monto_saldo_favor > 0`):
   - Crear `MovimientoCuentaCorriente` tipo=`'cargo'`, referencia_tipo=`'venta'`, monto=resto, referencia_id=venta.id

#### Ejemplo con pago simple CC:
- Venta: $1.000, forma_pago=`'cuenta_corriente'`
- Cliente tiene saldo a favor: $300
- Usuario elige consumir $300
- Movimiento 1: cargo $300, referencia_tipo=`'consumo_saldo_favor'`
- Movimiento 2: cargo $700, referencia_tipo=`'venta'`
- Saldo final: de -300 pasa a +700

#### Ejemplo con pago dividido:
- Venta: $1.000 (500 efectivo + 500 CC)
- Cliente tiene saldo a favor: $800
- El consumo actúa SOLO sobre los $500 de CC
- Default: consumir $500 (mínimo entre 800 y 500)
- Movimiento 1: cargo $500, referencia_tipo=`'consumo_saldo_favor'`
- No hay cargo adicional por CC (500 - 500 = 0)
- Saldo final: de -800 pasa a -300

#### Ejemplo con pago dividido y saldo menor:
- Venta: $1.000 (500 efectivo + 500 CC)
- Cliente tiene saldo a favor: $200
- Default: consumir $200
- Movimiento 1: cargo $200, referencia_tipo=`'consumo_saldo_favor'`
- Movimiento 2: cargo $300, referencia_tipo=`'venta'`
- Saldo final: de -200 pasa a +300

---

### Cambio 4: Anulación de venta que consumió saldo a favor

**Archivo**: `app/routes/ventas.py` (ruta anular)

**Lógica adicional**:
1. Al anular venta, buscar MovimientoCuentaCorriente con `referencia_tipo='consumo_saldo_favor'` y `referencia_id=venta.id`
2. Si existe: crear movimiento inverso:
   - tipo=`'pago'`
   - referencia_tipo=`'anulacion_consumo_saldo'`
   - monto= el monto que se había consumido
3. Esto RESTAURA el saldo a favor del cliente

**Ejemplo**:
- Venta consumió $300 de saldo a favor + $700 cargo normal
- Al anular:
  - Se revierte cargo de $700 (flujo existente, tipo='pago', referencia_tipo='anulacion_venta')
  - Se revierte consumo de $300 (NUEVO, tipo='pago', referencia_tipo='anulacion_consumo_saldo')
- Cliente vuelve a tener saldo a favor de $300

---

### Cambio 5: Nuevo concepto en MovimientoCaja

**Archivo**: `app/models/caja.py`

Agregar al enum `concepto_movimiento_caja`:
- Valor: `'adelanto_cliente'`
- Display: `'Adelanto de Cliente'`

**Migración**: `migrations/versions/0011_adelanto_cliente.py`
```sql
ALTER TYPE concepto_movimiento_caja ADD VALUE IF NOT EXISTS 'adelanto_cliente';
```

---

### Cambio 6: Nuevas propiedades en Cliente

**Archivo**: `app/models/cliente.py`

```python
@property
def tiene_saldo_a_favor(self):
    """Retorna True si el cliente tiene saldo a favor (crédito)."""
    return self.saldo_cuenta_corriente < 0

@property
def saldo_a_favor(self):
    """Retorna el monto de saldo a favor, o 0 si no tiene."""
    if self.saldo_cuenta_corriente < 0:
        return abs(self.saldo_cuenta_corriente)
    return Decimal('0')
```

---

### Cambio 7: Nuevo formulario

**Archivo**: `app/forms/cliente_forms.py`

```python
class AdelantoCuentaCorrienteForm(FlaskForm):
    monto = DecimalField(
        'Monto del adelanto',
        validators=[
            DataRequired(message='El monto es requerido'),
            NumberRange(min=0.01, message='El monto debe ser mayor a 0')
        ],
        places=2
    )
    forma_pago = SelectField(
        'Forma de Pago',
        choices=[
            ('efectivo', 'Efectivo'),
            ('tarjeta_debito', 'Tarjeta Débito'),
            ('tarjeta_credito', 'Tarjeta Crédito'),
            ('transferencia', 'Transferencia'),
            ('qr', 'QR')
        ]
    )
    motivo = StringField(
        'Motivo del adelanto',
        validators=[Optional(), Length(max=200)]
    )
```

---

### Cambio 8: Modificaciones en templates

#### `app/templates/clientes/cuenta_corriente.html`

**Saldo con 3 estados de color**:
- Rojo: saldo > 0 (deuda)
- Verde: saldo = 0 (sin saldo)
- Azul: saldo < 0 (saldo a favor) → mostrar como "Saldo a favor: $X.XX"

**Sección "Registrar Pago"**: se mantiene visible solo si `tiene_deuda` (sin cambios)

**Sección "Registrar Adelanto"**: siempre visible
- Formulario con: monto, forma de pago, motivo (campo de texto libre)
- Separado visualmente del formulario de pago

**Historial de movimientos**: badges diferenciados
- Cargo (rojo), Pago (verde), Adelanto (azul), Anulación (gris)

**Botón "Anular"** en movimientos tipo adelanto (solo visible para admin)

#### `app/templates/ventas/punto_venta.html`

**Badge informativo**: al seleccionar cliente con saldo a favor, mostrar badge "Saldo a favor: $X.XX"

**Sección condicional**: al elegir forma de pago CC (o dividido con porción CC):
- Texto: "Este cliente tiene $X.XX de saldo a favor"
- Input numérico: "Monto a consumir" con valor default
- Botón "Todo" para autocompletar con saldo disponible

---

### Cambio 9: Vista de clientes con saldo a favor

**Archivo**: `app/routes/clientes.py`
**Ruta**: `GET /clientes/con-saldo-a-favor`
**Decoradores**: `@login_required`, `@empresa_aprobada_required`

- Filtrar clientes con `saldo_cuenta_corriente < 0` y `activo=True`
- Mostrar: nombre, saldo a favor (abs), última fecha de adelanto
- Total de saldo a favor de la empresa
- Template similar a deudores

---

## Edge cases

| Caso | Comportamiento |
|------|---------------|
| Adelanto cuando cliente tiene deuda de $500, entrega $800 | Saldo pasa de +500 a -300. Queda con $300 a favor |
| Adelanto cuando cliente no tiene deuda, entrega $500 | Saldo pasa de 0 a -500. Queda con $500 a favor |
| Consumo mayor al monto CC de la venta | Bloqueado: consumo <= monto_cc |
| Consumo mayor al saldo disponible | Bloqueado: consumo <= abs(saldo_cuenta_corriente) |
| Anulación de adelanto ya anulado | Bloqueado: verificar que no exista movimiento con referencia_tipo='anulacion_adelanto' |
| Anulación de venta que consumió saldo a favor | Se restaura el saldo a favor (movimiento inverso) |
| Adelanto con caja cerrada | Bloqueado por @caja_abierta_required |
| Venta dividido $1000 (500 efectivo + 500 CC), saldo a favor $800 | Consumo actúa sobre los $500 de CC. Default: $500. Saldo: -800 → -300 |
| Venta dividido $1000 (500 efectivo + 500 CC), saldo a favor $200 | Default: $200. Cargo CC restante: $300. Saldo: -200 → +300 |
| Cliente sin limite_credito (=0) pero con saldo a favor | `puede_comprar_a_credito()` retorna False (limite <= 0). Evaluar si se permite usar saldo sin límite |
| Venta CC donde consumo = total | Solo MovimientoCuentaCorriente de consumo_saldo_favor, sin cargo adicional |
| Usuario intenta consumir $0 | Se ignora, flujo normal sin consumo |

---

## Cambios técnicos — resumen

### Archivos nuevos

| Archivo | Descripción |
|---------|-------------|
| `migrations/versions/0011_adelanto_cliente.py` | ALTER TYPE para agregar 'adelanto_cliente' a enum concepto_movimiento_caja |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `app/models/cliente.py` | Agregar propiedades `tiene_saldo_a_favor` y `saldo_a_favor` |
| `app/models/caja.py` | Agregar `'adelanto_cliente'` al enum y display |
| `app/forms/cliente_forms.py` | Agregar `AdelantoCuentaCorrienteForm` |
| `app/routes/clientes.py` | Agregar rutas: registrar-adelanto, anular-adelanto, con-saldo-a-favor |
| `app/routes/ventas.py` | Modificar punto_de_venta y anular para manejar consumo de saldo a favor |
| `app/templates/clientes/cuenta_corriente.html` | Saldo tricolor, sección adelanto, badges, botón anular |
| `app/templates/ventas/punto_venta.html` | Badge saldo a favor, sección consumo con input y botón "Todo" |

### Valores nuevos de referencia_tipo en MovimientoCuentaCorriente

| Valor | Uso | Longitud |
|-------|-----|----------|
| `'adelanto'` | Registro de adelanto | 8 chars |
| `'anulacion_adelanto'` | Anulación de adelanto | 20 chars |
| `'consumo_saldo_favor'` | Consumo en venta | 19 chars (límite String(20)) |
| `'anulacion_consumo_saldo'` | Anulación de consumo | ⚠️ 24 chars — NO CABE en String(20) |

**Nota**: `'anulacion_consumo_saldo'` excede String(20). Opciones:
1. Usar `'anul_consumo_saldo'` (19 chars) ✓
2. Ampliar columna a String(30) con migración

---

## Riesgos y consideraciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Saldo negativo confunde al ferretero | Medio | UI clara: azul = a favor, rojo = deuda. Nunca mostrar números negativos, siempre "Saldo a favor: $X" |
| Adelanto registrado por error | Medio | Ruta de anulación con @admin_required y confirmación |
| Consumo de saldo a favor complica el POS | Alto | Sección condicional, solo aparece cuando las 3 condiciones se cumplen. No rompe flujo existente |
| Anulación de venta con consumo de saldo | Medio | Lógica adicional en anular(), testeada con edge cases |
| `referencia_tipo` String(20) se queda corto | Bajo | Evaluar migración a String(30) o usar abreviaciones |

---

## Fases de implementación

### Fase 1: Registrar y anular adelantos
- Migración de enum
- Propiedades en Cliente
- Formulario AdelantoCuentaCorrienteForm
- Ruta registrar-adelanto con MovimientoCuentaCorriente + MovimientoCaja
- Ruta anular-adelanto (admin only)
- Template: saldo tricolor, sección adelanto, botón anular
- Vista clientes con saldo a favor

**Criterios de aceptación**:
- Se puede registrar un adelanto y el saldo queda negativo
- Se puede anular un adelanto y el saldo se restaura
- El historial muestra los movimientos correctamente
- MovimientoCaja registra el ingreso en la caja abierta

### Fase 2: Consumo de saldo a favor en ventas
- Modificar punto_de_venta (backend) para recibir monto_saldo_favor
- Validaciones de consumo
- Crear MovimientoCuentaCorriente de consumo
- Modificar anulación de ventas para restaurar saldo
- Template POS: badge, sección consumo, input, botón "Todo"

**Criterios de aceptación**:
- Al seleccionar cliente con saldo a favor y forma de pago CC, aparece opción de consumo
- Se puede elegir cuánto consumir (parcial o total)
- En dividido, el consumo actúa solo sobre la porción CC
- Al anular venta, se restaura el saldo a favor consumido

---

## Validación realizada

Este plan fue validado exhaustivamente contra el codebase por un agente auditor. Se encontraron y resolvieron:

- **3 errores graves**: anulación de adelanto, flujo incompleto de consumo en ventas, anulación de venta con consumo
- **5 advertencias**: caja abierta explícita, vista de clientes con saldo, templates con tiene_deuda, UX del POS, inconsistencia de decoradores

Todas las observaciones fueron incorporadas en esta versión del plan.
