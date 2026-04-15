# Feature: Gestion Avanzada de Cuenta Corriente

## Resumen ejecutivo

Esta feature extiende el sistema de cuenta corriente existente en FerrERP con dos capacidades nuevas:

1. **Estado de Cuenta PDF**: Generacion de un documento PDF descargable/imprimible con el resumen de deuda, movimientos recientes y detalle de compras del cliente. Pensado para que el ferretero se lo mande por WhatsApp o lo imprima y se lo entregue.

2. **Ajuste de saldos por actualizacion de precios**: Cuando se ejecuta una actualizacion masiva de precios, el sistema ofrece la opcion de recalcular las deudas pendientes de cuenta corriente para reflejar los precios nuevos. Esto protege al ferretero de la perdida por inflacion cuando vende a credito.

---

## Contexto y problema de negocio

### La realidad de la ferreteria argentina

En Argentina, la inflacion hace que los precios de los productos cambien constantemente. Un ferretero actualiza precios con frecuencia -- a veces cada semana, a veces cada quince dias. FerrERP ya tiene una feature de actualizacion masiva de precios por categoria con porcentaje que resuelve esa necesidad.

El problema aparece cuando el ferretero vende a cuenta corriente. El flujo actual es:

1. El cliente compra productos por cuenta corriente
2. Se registra un `MovimientoCuentaCorriente` tipo `cargo` con el total de la venta
3. El precio se congela en `VentaDetalle.precio_unitario` al momento de la venta
4. Pasan dias o semanas hasta que el cliente viene a pagar
5. En ese tiempo, los precios subieron

**El ferretero pierde plata.** Vendio a $1.000 lo que ahora vale $1.100. Cuando cobra, recibe pesos que valen menos de lo que valio la mercaderia que entrego. No tiene manera de ajustar esas deudas salvo hacerlo manualmente, una por una, calculando diferencias a mano.

### Ejemplo concreto

| Paso | Accion | Deuda del cliente |
|------|--------|-------------------|
| 1 | El cliente compra un martillo ($1.000) y un destornillador ($1.000) por CC | $2.000 |
| 2 | El ferretero aplica actualizacion masiva del 10% | $2.000 (sin cambios) |
| 3 | **Con esta feature**: el sistema recalcula y genera un cargo de ajuste por $200 | **$2.200** |
| 4 | El cliente paga $1.000 | $1.200 |

Sin esta feature, en el paso 3 la deuda seguiria siendo $2.000 y el ferretero perderia $200.

### El segundo pain point: comunicacion con el cliente

El otro problema es que el ferretero no tiene una forma prolija de mostrarle al cliente cuanto debe y que compro. Hoy puede mostrar la pantalla del sistema, pero necesita algo que pueda:

- Imprimir y darle en mano
- Mandar por WhatsApp como PDF
- Usar como comprobante si hay alguna discusion sobre la deuda

---

## Parte 1: Estado de Cuenta PDF

### Requerimientos funcionales

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| PDF-01 | Generar PDF de estado de cuenta desde la vista de cuenta corriente del cliente | Alta |
| PDF-02 | Incluir datos del negocio (nombre, CUIT, direccion, telefono, logo) | Alta |
| PDF-03 | Incluir datos del cliente (nombre, DNI/CUIT, telefono, direccion) | Alta |
| PDF-04 | Mostrar saldo actual, limite de credito y credito disponible | Alta |
| PDF-05 | Listar ultimos N movimientos (cargos y pagos) con fecha, tipo, descripcion, monto | Alta |
| PDF-06 | Incluir detalle de las ultimas compras por CC con productos (nombre, cantidad, precio unitario, subtotal) | Alta |
| PDF-07 | Incluir fecha de emision y numero de referencia | Alta |
| PDF-08 | Incluir leyenda al pie con condiciones o mensaje personalizable | Media |
| PDF-09 | Permitir elegir el rango de fechas de los movimientos a incluir | Baja |
| PDF-10 | Reutilizar la infraestructura de PDF existente (WeasyPrint + `pdf_utils.obtener_config_negocio`) | Alta |

### Datos incluidos en el PDF

**Encabezado:**
- Logo de la empresa (si existe, via `obtener_logo_base64()`)
- Nombre del negocio, CUIT, direccion, telefono, email (via `obtener_config_negocio()`)
- Titulo: "Estado de Cuenta"
- Fecha de emision
- Numero de referencia: `EC-{cliente_id}-{timestamp}`

**Datos del cliente:**
- Nombre (`Cliente.nombre`)
- DNI/CUIT (`Cliente.dni_cuit`)
- Telefono (`Cliente.telefono`)
- Direccion (`Cliente.direccion`)

**Resumen financiero:**
- Saldo actual (deuda): `Cliente.saldo_cuenta_corriente`
- Limite de credito: `Cliente.limite_credito`
- Credito disponible: `Cliente.credito_disponible`

**Tabla de movimientos recientes** (ultimos 20 por defecto):
- Fecha
- Tipo (Cargo / Pago)
- Descripcion
- Monto
- Saldo posterior

**Detalle de compras pendientes** (ventas por CC no totalmente pagadas):
- Numero de venta (`Venta.numero_completo`)
- Fecha de la venta
- Por cada item: nombre del producto, cantidad, precio unitario, subtotal
- Total de la venta
- Si hubo ajustes de precio, mostrarlos

**Pie:**
- Leyenda configurable (ej: "Los precios estan sujetos a actualizacion")
- Fecha y hora de generacion

### Wireframe textual del PDF

```
+------------------------------------------------------------------+
|  [LOGO]   FERRETERIA EL TORNILLO                                 |
|            CUIT: 20-12345678-9                                   |
|            Av. San Martin 1234, CABA                             |
|            Tel: (011) 4567-8901                                  |
+------------------------------------------------------------------+
|                    ESTADO DE CUENTA                               |
|  Ref: EC-42-20260412          Fecha: 12/04/2026                  |
+------------------------------------------------------------------+
|  CLIENTE                                                         |
|  Nombre: Juan Perez                                              |
|  DNI/CUIT: 20-33445566-7                                         |
|  Telefono: (011) 1234-5678                                       |
|  Direccion: Calle Falsa 123, CABA                                |
+------------------------------------------------------------------+
|  RESUMEN                                                         |
|  +-----------------------------+                                 |
|  | Saldo actual (deuda)  | $12.500,00  |                        |
|  | Limite de credito      | $50.000,00  |                        |
|  | Credito disponible     | $37.500,00  |                        |
|  +-----------------------------+                                 |
+------------------------------------------------------------------+
|  MOVIMIENTOS RECIENTES                                           |
|  +-------+--------+---------------------------+----------+-------+
|  | Fecha | Tipo   | Descripcion               | Monto    | Saldo |
|  +-------+--------+---------------------------+----------+-------+
|  | 10/04 | Cargo  | Venta #2026-000145        | $5.500   | $12.5 |
|  | 08/04 | Pago   | Pago en efectivo          | -$3.000  | $7.0  |
|  | 05/04 | Cargo  | Venta #2026-000138        | $4.000   | $10.0 |
|  | 05/04 | Cargo  | Ajuste por act. precios   | $1.000   | $6.0  |
|  | 01/04 | Cargo  | Venta #2026-000130        | $5.000   | $5.0  |
|  +-------+--------+---------------------------+----------+-------+
+------------------------------------------------------------------+
|  DETALLE DE COMPRAS RECIENTES                                    |
|                                                                  |
|  Venta #2026-000145 - 10/04/2026                                 |
|  +-------------------------------------------+-----+------+-----+
|  | Producto                                  | Cant| P.U. | Subt|
|  +-------------------------------------------+-----+------+-----+
|  | Martillo Stanley 500g                     | 1   | $3.0 | $3.0|
|  | Tornillos autop. 6x1" (caja x100)        | 5   | $500 | $2.5|
|  +-------------------------------------------+-----+------+-----+
|  |                                     Total: $5.500,00         |
|  +--------------------------------------------------------------+
|                                                                  |
|  Venta #2026-000138 - 05/04/2026                                 |
|  +-------------------------------------------+-----+------+-----+
|  | Cinta metrica 5m                          | 2   | $1.5 | $3.0|
|  | Llave francesa 10"                        | 1   | $1.0 | $1.0|
|  +-------------------------------------------+-----+------+-----+
|  |                                     Total: $4.000,00         |
|  +--------------------------------------------------------------+
+------------------------------------------------------------------+
|  Los precios estan sujetos a actualizacion.                      |
|  Documento generado el 12/04/2026 a las 14:30.                  |
+------------------------------------------------------------------+
```

### Ruta y servicio propuestos

**Ruta nueva:**

```python
# app/routes/clientes.py

@bp.route('/<int:id>/estado-cuenta-pdf')
@login_required
def estado_cuenta_pdf(id):
    """Genera y descarga el PDF de estado de cuenta del cliente."""
    cliente = Cliente.get_o_404(id)
    pdf_bytes = cuenta_corriente_service.generar_estado_cuenta_pdf(cliente)
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename=estado_cuenta_{cliente.id}.pdf'
        }
    )
```

**Servicio nuevo:**

```python
# app/services/cuenta_corriente_service.py

def generar_estado_cuenta_pdf(cliente, cantidad_movimientos=20):
    """Genera PDF de estado de cuenta para un cliente."""
    from weasyprint import HTML
    from flask import render_template
    from .pdf_utils import obtener_config_negocio

    negocio = obtener_config_negocio()

    # Ultimos movimientos
    movimientos = (
        MovimientoCuentaCorriente.query
        .filter_by(cliente_id=cliente.id)
        .order_by(MovimientoCuentaCorriente.created_at.desc())
        .limit(cantidad_movimientos)
        .all()
    )

    # Ventas por CC pendientes (con saldo > 0)
    ventas_cc = obtener_ventas_cc_pendientes(cliente)

    html = render_template(
        'clientes/pdf/estado_cuenta.html',
        negocio=negocio,
        cliente=cliente,
        movimientos=movimientos,
        ventas_cc=ventas_cc,
        fecha_emision=ahora_argentina(),
    )
    return HTML(string=html).write_pdf()
```

**Template nuevo:**

```
app/templates/clientes/pdf/estado_cuenta.html
```

Siguiendo el mismo patron que `app/templates/ventas/pdf/venta.html` y `app/templates/presupuestos/pdf/presupuesto.html`.

**Boton en la UI:**

Agregar un boton "Descargar Estado de Cuenta" en la vista existente `clientes/cuenta_corriente.html`, al lado de los controles actuales.

---

## Parte 2: Ajuste de Saldos por Actualizacion de Precios

### Requerimientos funcionales

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| AJ-01 | Al ejecutar actualizacion masiva de precios, ofrecer opcion de recalcular saldos de CC pendientes | Alta |
| AJ-02 | Mostrar preview de los ajustes antes de aplicar (lista de clientes afectados con monto original, monto nuevo, diferencia) | Alta |
| AJ-03 | Registrar cada ajuste como `MovimientoCuentaCorriente` tipo `cargo` con `referencia_tipo='ajuste_precio'` | Alta |
| AJ-04 | Trackear que ventas ya fueron ajustadas para evitar ajustes duplicados | Alta |
| AJ-05 | Solo afectar ventas por CC que NO estan totalmente pagadas | Alta |
| AJ-06 | El ajuste es OPCIONAL: el ferretero decide si lo aplica o no | Alta |
| AJ-07 | El ajuste debe ser visible en el estado de cuenta del cliente como "Ajuste por actualizacion de precios" | Alta |
| AJ-08 | Registrar auditoria: que actualizacion de precios genero el ajuste, que ventas se afectaron, montos originales y nuevos | Alta |
| AJ-09 | Manejar correctamente pagos parciales: solo ajustar sobre el saldo pendiente | Alta |
| AJ-10 | Permitir ajustar solo para ciertas categorias (las mismas que se actualizaron) | Media |

### Flujo de usuario paso a paso

```
1. El admin va a Productos > Actualizacion Masiva de Precios
2. Selecciona categoria(s) y porcentaje (flujo existente)
3. Ve el preview de productos que se van a actualizar (flujo existente)
4. NUEVO: Debajo del preview de productos, aparece una seccion:
   "Ajustar saldos de cuenta corriente"
   [ ] Recalcular deudas pendientes con los precios nuevos
5. Si marca el checkbox, aparece un segundo preview (via HTMX):
   +--------------------------------------------------+
   | Cliente          | Deuda actual | Ajuste | Nueva |
   +--------------------------------------------------+
   | Juan Perez       | $12.000      | +$800  | $12.8 |
   | Maria Garcia     | $5.500       | +$350  | $5.85 |
   +--------------------------------------------------+
   | Total ajustes:                    $1.150          |
   +--------------------------------------------------+
   Con detalle expandible por cliente mostrando las ventas afectadas.
6. El admin confirma y aplica la actualizacion masiva + ajustes de CC
7. Se aplican los cambios de precio (flujo existente)
8. Se generan los MovimientoCuentaCorriente de ajuste
9. Se muestra mensaje de exito con resumen
```

### Modelo de datos: cambios necesarios

#### Nuevo modelo: `AjustePrecioCuentaCorriente`

```python
# app/models/ajuste_precio_cc.py

class AjustePrecioCuentaCorriente(EmpresaMixin, db.Model):
    """Registro de ajuste de saldo de cuenta corriente por actualizacion de precios."""

    __tablename__ = 'ajustes_precio_cuenta_corriente'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False, index=True)
    movimiento_cc_id = db.Column(
        db.Integer,
        db.ForeignKey('movimientos_cuenta_corriente.id'),
        nullable=False
    )
    actualizacion_fecha = db.Column(db.DateTime, nullable=False)
    porcentaje_aplicado = db.Column(db.Numeric(8, 4), nullable=False)
    total_original = db.Column(db.Numeric(12, 2), nullable=False)
    total_recalculado = db.Column(db.Numeric(12, 2), nullable=False)
    monto_ajuste = db.Column(db.Numeric(12, 2), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=ahora_argentina)

    # Relaciones
    cliente = db.relationship('Cliente')
    venta = db.relationship('Venta')
    movimiento_cc = db.relationship('MovimientoCuentaCorriente')
    usuario = db.relationship('Usuario')
```

**Proposito:** Este modelo es la tabla de auditoria que permite saber exactamente que se ajusto, por cuanto, a raiz de que actualizacion, y sobre que venta. Tambien sirve para evitar ajustes duplicados: si una venta ya tiene un `AjustePrecioCuentaCorriente` con una `actualizacion_fecha` posterior a la venta, no se vuelve a ajustar por la misma actualizacion.

#### Cambios en modelos existentes

**`MovimientoCuentaCorriente`:**
- El campo `referencia_tipo` ya acepta strings arbitrarios (`db.String(20)`). Se usara el valor `'ajuste_precio'` para identificar estos movimientos.
- No hace falta migrar la columna, solo documentar el nuevo valor.

**`VentaDetalle`:**
- No se modifica. El `precio_unitario` sigue siendo el snapshot al momento de la venta. El recalculo usa el `Producto.precio_venta` actual para calcular la diferencia.

### Logica de recalculo (algoritmo)

```
FUNCION calcular_ajustes_cc(categoria_ids, porcentaje):
    ajustes = []

    # 1. Obtener productos afectados por la actualizacion
    productos_actualizados = Producto.query.filter(
        Producto.categoria_id.in_(categoria_ids)
    ).all()
    productos_ids = {p.id for p in productos_actualizados}

    # 2. Obtener ventas por CC con saldo pendiente
    ventas_cc_pendientes = obtener_ventas_cc_pendientes_con_detalles()
    #    Esto busca ventas donde:
    #    - forma_pago IN ('cuenta_corriente', 'dividido')
    #    - estado = 'completada'
    #    - tiene MovimientoCuentaCorriente tipo 'cargo' sin pago total equivalente
    #    - NO fue anulada

    PARA CADA venta EN ventas_cc_pendientes:
        # 3. Calcular monto de CC de esta venta
        monto_cc_venta = calcular_monto_cc(venta)

        # 4. Filtrar detalles que tienen productos afectados
        detalles_afectados = [
            d for d in venta.detalles
            if d.producto_id in productos_ids
        ]

        SI NO detalles_afectados:
            CONTINUAR

        # 5. Verificar que no se haya ajustado ya esta venta por esta actualizacion
        ya_ajustado = AjustePrecioCuentaCorriente.query.filter_by(
            venta_id=venta.id,
            actualizacion_fecha=fecha_actualizacion
        ).first()

        SI ya_ajustado:
            CONTINUAR

        # 6. Calcular diferencia
        total_original = sum(d.subtotal for d in detalles_afectados)
        total_recalculado = sum(
            calcular_subtotal_recalculado(d, porcentaje)
            for d in detalles_afectados
        )
        diferencia = total_recalculado - total_original

        SI diferencia <= 0:
            CONTINUAR

        # 7. Ajustar proporcionalmente si hay pago parcial
        ratio_pendiente = calcular_ratio_pendiente(venta, monto_cc_venta)
        monto_ajuste = diferencia * ratio_pendiente

        ajustes.append({
            'cliente': venta.cliente,
            'venta': venta,
            'total_original': total_original,
            'total_recalculado': total_recalculado,
            'diferencia': diferencia,
            'ratio_pendiente': ratio_pendiente,
            'monto_ajuste': monto_ajuste,
        })

    RETORNAR ajustes
```

#### Funcion auxiliar: `calcular_subtotal_recalculado`

```
FUNCION calcular_subtotal_recalculado(detalle, porcentaje):
    # Aplicar el porcentaje de aumento al precio unitario original
    precio_nuevo = detalle.precio_unitario * (1 + porcentaje / 100)
    bruto = detalle.cantidad * precio_nuevo
    descuento = bruto * (detalle.descuento_porcentaje / 100)
    RETORNAR bruto - descuento
```

**Nota importante:** Se usa el `precio_unitario` del detalle (snapshot) + porcentaje, y NO el `Producto.precio_venta` actual. Esto es porque el producto puede haber tenido actualizaciones manuales de precio ademas de la masiva, y usar el precio actual podria generar un ajuste incorrecto. Al aplicar el mismo porcentaje que la actualizacion masiva, el calculo es exacto y trazable.

#### Funcion auxiliar: `calcular_ratio_pendiente`

```
FUNCION calcular_ratio_pendiente(venta, monto_cc_venta):
    # Sumar pagos realizados contra esta venta
    pagos = MovimientoCuentaCorriente.query.filter_by(
        referencia_tipo='pago',
        referencia_id=venta.id
    ).all()
    total_pagado = sum(p.monto for p in pagos)

    # Ratio de lo que queda pendiente
    SI monto_cc_venta <= 0:
        RETORNAR 0

    pendiente = monto_cc_venta - total_pagado
    SI pendiente <= 0:
        RETORNAR 0

    RETORNAR pendiente / monto_cc_venta
```

**Ejemplo con pago parcial:**
- Venta de $2.000, el cliente pago $500, queda debiendo $1.500
- Ratio pendiente: 1500 / 2000 = 0.75
- Si la actualizacion genera una diferencia de $200 sobre el total de la venta
- Ajuste = $200 * 0.75 = $150 (solo se ajusta la proporcion que todavia debe)

#### Funcion de aplicacion

```
FUNCION aplicar_ajustes_cc(ajustes, usuario_id, fecha_actualizacion):
    PARA CADA ajuste EN ajustes:
        cliente = ajuste['cliente']

        # 1. Actualizar saldo del cliente
        saldo_anterior, saldo_posterior = cliente.actualizar_saldo(
            ajuste['monto_ajuste'], tipo='cargo'
        )

        # 2. Crear movimiento de cuenta corriente
        movimiento = MovimientoCuentaCorriente(
            cliente_id=cliente.id,
            tipo='cargo',
            monto=ajuste['monto_ajuste'],
            saldo_anterior=saldo_anterior,
            saldo_posterior=saldo_posterior,
            referencia_tipo='ajuste_precio',
            referencia_id=ajuste['venta'].id,
            descripcion=f'Ajuste por actualizacion de precios ({ajuste["diferencia"]:.2f} sobre venta #{ajuste["venta"].numero_completo})',
            usuario_id=usuario_id,
            empresa_id=cliente.empresa_id,
        )
        db.session.add(movimiento)
        db.session.flush()  # Para obtener movimiento.id

        # 3. Crear registro de auditoria
        registro = AjustePrecioCuentaCorriente(
            cliente_id=cliente.id,
            venta_id=ajuste['venta'].id,
            movimiento_cc_id=movimiento.id,
            actualizacion_fecha=fecha_actualizacion,
            porcentaje_aplicado=porcentaje,
            total_original=ajuste['total_original'],
            total_recalculado=ajuste['total_recalculado'],
            monto_ajuste=ajuste['monto_ajuste'],
            usuario_id=usuario_id,
            empresa_id=cliente.empresa_id,
        )
        db.session.add(registro)

    db.session.commit()
```

### Consideraciones de edge cases

| Edge case | Comportamiento |
|-----------|----------------|
| **Venta totalmente pagada** | Se excluye del calculo. Si `ratio_pendiente == 0`, no se genera ajuste. |
| **Venta anulada** | Se excluye. Solo se consideran ventas con `estado='completada'`. |
| **Venta con pago dividido (CC + efectivo)** | Solo se considera la porcion de CC (`VentaPago` con `forma_pago='cuenta_corriente'`). El `monto_cc_venta` es el monto del `VentaPago` de CC, no el total de la venta. |
| **Producto sin stock / eliminado** | El `VentaDetalle` tiene el `producto_id` como FK. Si el producto se desactivo, igual tiene el snapshot del precio. Se usa el porcentaje, no el precio actual del producto. |
| **Doble actualizacion masiva** | El campo `actualizacion_fecha` en `AjustePrecioCuentaCorriente` evita que se ajuste la misma venta dos veces por la misma actualizacion. Pero si hay DOS actualizaciones distintas, se aplican ambos ajustes (porque cada una es un evento diferente). |
| **Actualizacion con porcentaje negativo (baja de precios)** | Si `diferencia <= 0`, no se genera ajuste. No se hacen notas de credito automaticas por baja de precios. Esta es una decision de negocio: el ajuste es para proteger al ferretero de la inflacion, no para perjudicarlo si baja un precio. |
| **Cliente con limite de credito superado post-ajuste** | El ajuste se aplica igual. El limite de credito es una restriccion para NUEVAS compras, no para ajustes de deuda existente. Se podria agregar un warning en el preview. |
| **Venta con descuento por item** | El `calcular_subtotal_recalculado` respeta el `descuento_porcentaje` del detalle. El descuento se aplica sobre el precio nuevo, no se pierde. |
| **Multiples ventas del mismo cliente** | Se generan ajustes separados por venta (un `MovimientoCuentaCorriente` por venta ajustada). Esto da trazabilidad completa. |

---

## Cambios tecnicos necesarios

### Archivos nuevos

| Archivo | Descripcion |
|---------|-------------|
| `app/models/ajuste_precio_cc.py` | Modelo `AjustePrecioCuentaCorriente` |
| `app/services/cuenta_corriente_service.py` | Servicio con logica de generacion de PDF y calculo/aplicacion de ajustes |
| `app/templates/clientes/pdf/estado_cuenta.html` | Template WeasyPrint para el PDF de estado de cuenta |
| `app/templates/productos/_preview_ajuste_cc.html` | Partial HTMX con el preview de ajustes de CC (se muestra dentro de la actualizacion masiva) |
| `migrations/versions/xxx_ajuste_precio_cc.py` | Migracion Alembic para la tabla `ajustes_precio_cuenta_corriente` |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `app/models/__init__.py` | Importar y exportar `AjustePrecioCuentaCorriente` |
| `app/routes/clientes.py` | Agregar ruta `estado_cuenta_pdf` |
| `app/routes/productos.py` | Modificar flujo de actualizacion masiva para incluir opcion de ajuste de CC (preview y aplicacion) |
| `app/templates/clientes/cuenta_corriente.html` | Agregar boton "Descargar Estado de Cuenta" |
| `app/templates/productos/actualizacion_masiva.html` | Agregar seccion de checkbox + preview de ajustes de CC |

### Servicios nuevos (detalle)

**`app/services/cuenta_corriente_service.py`:**

```python
# Funciones principales:

def generar_estado_cuenta_pdf(cliente, cantidad_movimientos=20):
    """Genera PDF de estado de cuenta."""

def obtener_ventas_cc_pendientes(cliente):
    """Obtiene ventas por CC del cliente que tienen saldo pendiente."""

def calcular_ajustes_cc(categoria_ids, porcentaje, empresa_id):
    """Calcula preview de ajustes sin aplicarlos."""

def aplicar_ajustes_cc(ajustes, usuario_id, fecha_actualizacion, porcentaje):
    """Aplica los ajustes y genera movimientos + registros de auditoria."""

def calcular_monto_cc(venta):
    """Calcula el monto de CC de una venta (completa o dividida)."""

def calcular_ratio_pendiente(venta, monto_cc_venta):
    """Calcula que proporcion de la deuda de una venta sigue pendiente."""
```

### Migraciones

Una sola migracion que crea la tabla `ajustes_precio_cuenta_corriente`:

```sql
CREATE TABLE ajustes_precio_cuenta_corriente (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    venta_id INTEGER NOT NULL REFERENCES ventas(id),
    movimiento_cc_id INTEGER NOT NULL REFERENCES movimientos_cuenta_corriente(id),
    actualizacion_fecha TIMESTAMP NOT NULL,
    porcentaje_aplicado NUMERIC(8,4) NOT NULL,
    total_original NUMERIC(12,2) NOT NULL,
    total_recalculado NUMERIC(12,2) NOT NULL,
    monto_ajuste NUMERIC(12,2) NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_ajustes_precio_cc_cliente ON ajustes_precio_cuenta_corriente(cliente_id);
CREATE INDEX ix_ajustes_precio_cc_venta ON ajustes_precio_cuenta_corriente(venta_id);
CREATE INDEX ix_ajustes_precio_cc_fecha ON ajustes_precio_cuenta_corriente(actualizacion_fecha);
```

---

## Riesgos y consideraciones

| Riesgo | Impacto | Mitigacion |
|--------|---------|------------|
| **Ajuste incorrecto por error en porcentaje** | El cliente termina con una deuda mayor a la real | El preview obligatorio antes de aplicar permite al ferretero revisar los montos. Ademas, el registro de auditoria permite identificar y revertir un ajuste erroneo. |
| **Confusion del cliente al ver ajustes** | El cliente no entiende por que su deuda aumento | El estado de cuenta PDF muestra claramente "Ajuste por actualizacion de precios" con el monto discriminado. |
| **Performance con muchos clientes/ventas** | El calculo del preview podria ser lento | Usar queries optimizadas con JOINs. El calculo es un preview one-shot, no una operacion recurrente. Si hay muchos clientes, paginar el preview. |
| **Inconsistencia si se interrumpe la aplicacion** | Algunos clientes quedan ajustados y otros no | Envolver toda la aplicacion de ajustes en una transaccion de base de datos. Si falla, rollback completo. |
| **Actualizacion de precios sin ajuste de CC y posterior ajuste manual** | El ferretero podria querer ajustar CC despues, no en el momento | Considerar en Fase 2 una opcion de "Ajustar CC de actualizacion pasada" accesible desde un historial de actualizaciones. Para la v1, el ajuste solo se ofrece al momento de la actualizacion masiva. |
| **Ventas divididas con porcion de CC** | El monto de CC es menor que el total de la venta, lo cual complica el calculo proporcional | `calcular_monto_cc()` obtiene el monto exacto de CC desde `VentaPago`. El ratio pendiente se calcula sobre ese monto, no sobre el total de la venta. |

---

## Fases de implementacion sugeridas

### Fase 1: Estado de Cuenta PDF

**Estimacion:** 1-2 dias de desarrollo

**Alcance:**
- Crear `app/services/cuenta_corriente_service.py` con `generar_estado_cuenta_pdf()`
- Crear template `app/templates/clientes/pdf/estado_cuenta.html`
- Agregar ruta `/<int:id>/estado-cuenta-pdf` en `app/routes/clientes.py`
- Agregar boton en `clientes/cuenta_corriente.html`
- Funcion auxiliar `obtener_ventas_cc_pendientes()` (se reutiliza en Fase 2)

**Criterios de aceptacion:**
- Se puede descargar un PDF desde la vista de cuenta corriente de un cliente
- El PDF incluye todos los datos especificados (negocio, cliente, saldo, movimientos, compras)
- El PDF se ve bien impreso y en pantalla
- Funciona con y sin logo configurado
- Los movimientos tipo `ajuste_precio` se muestran correctamente (forward-compatible con Fase 2)

### Fase 2: Modelo de auditoria y logica de calculo

**Estimacion:** 2-3 dias de desarrollo

**Alcance:**
- Crear modelo `AjustePrecioCuentaCorriente`
- Migracion de base de datos
- Implementar `calcular_ajustes_cc()` con toda la logica de recalculo
- Implementar `aplicar_ajustes_cc()`
- Tests unitarios del algoritmo (edge cases de pagos parciales, ventas divididas, duplicados)

**Criterios de aceptacion:**
- El calculo devuelve ajustes correctos para ventas simples de CC
- Maneja correctamente ventas con pago parcial (ratio proporcional)
- Maneja correctamente ventas divididas (solo porcion CC)
- No genera ajustes duplicados para la misma venta + misma actualizacion
- No genera ajustes para ventas totalmente pagadas o anuladas
- La aplicacion de ajustes es atomica (transaccion completa o rollback)

### Fase 3: Integracion con actualizacion masiva de precios

**Estimacion:** 1-2 dias de desarrollo

**Alcance:**
- Modificar `app/routes/productos.py` para incluir opcion de ajuste de CC
- Crear partial `_preview_ajuste_cc.html` con tabla de preview
- Modificar `app/templates/productos/actualizacion_masiva.html` para el checkbox y el contenedor HTMX
- Ruta nueva para el preview HTMX de ajustes de CC
- Integracion del apply: al confirmar actualizacion masiva con ajuste de CC, ejecutar ambos

**Criterios de aceptacion:**
- Aparece checkbox "Recalcular deudas de cuenta corriente" en la pantalla de actualizacion masiva
- Al marcar el checkbox, se muestra un preview con los clientes afectados y los montos
- Al aplicar, se generan los `MovimientoCuentaCorriente` y los registros de auditoria
- Los ajustes aparecen correctamente en la vista de cuenta corriente del cliente
- El estado de cuenta PDF refleja los ajustes

### Fase 4 (opcional): Mejoras post-lanzamiento

**Alcance potencial:**
- Filtro de rango de fechas en el estado de cuenta PDF
- Ajuste retroactivo de CC desde historial de actualizaciones
- Notificacion/badge cuando hay ajustes pendientes de aplicar
- Reporte consolidado de ajustes de CC aplicados
- Opcion de revertir un ajuste especifico

---

## Validacion contra el codebase (2026-04-13)

Se realizo una inspeccion exhaustiva del codebase para validar cada afirmacion tecnica de este documento.

### Verificaciones CORRECTAS

| Componente | Estado | Detalle |
|-----------|--------|---------|
| MovimientoCuentaCorriente | ✅ OK | Todos los campos coinciden. `referencia_tipo` es String(20), flexible para el nuevo valor `'ajuste_precio'` |
| Cliente | ✅ OK | `saldo_cuenta_corriente`, `limite_credito`, `actualizar_saldo()`, `puede_comprar_a_credito()`, `tiene_deuda`, `credito_disponible` — todos existen |
| Venta | ✅ OK | Enum forma_pago incluye `'cuenta_corriente'` y `'dividido'` |
| VentaDetalle | ✅ OK | `precio_unitario`, `cantidad`, `descuento_porcentaje`, `subtotal`, `calcular_subtotal()` — todo correcto |
| VentaPago | ✅ OK | `forma_pago` (sin 'dividido'), `monto`, `venta_id` |
| Producto y ActualizacionPrecio | ✅ OK | Todos los campos y relaciones coinciden |
| Rutas existentes | ✅ OK | cuenta-corriente, registrar-pago, deudores, actualizacion-masiva — todas existen y hacen lo que dice el doc |
| Servicios existentes | ✅ OK | pdf_utils, venta_service, actualizacion_precio_service — coinciden exactamente |
| Templates existentes | ✅ OK | cuenta_corriente.html, ventas/pdf/venta.html, actualizacion_masiva.html |

### PROBLEMA CRITICO encontrado: vinculacion pagos ↔ ventas

**El algoritmo `calcular_ratio_pendiente()` propuesto en este documento es INVIABLE con la arquitectura actual.**

**Evidencia:** En `app/routes/clientes.py` linea 211-221, cuando se registra un pago de CC:

```python
movimiento_cc = MovimientoCuentaCorriente(
    cliente_id=cliente.id,
    tipo='pago',
    monto=monto,
    referencia_tipo='pago',
    # referencia_id NO se asigna — no se vincula a una venta especifica
    descripcion=form.descripcion.data or 'Pago de cuenta corriente',
)
```

Los pagos van contra el **saldo general del cliente**, no contra una venta puntual. El algoritmo propuesto intenta buscar pagos por `referencia_id=venta.id`, lo cual siempre devolveria 0 resultados → ratio siempre seria 1.0 → ajustes incorrectos.

### Decisiones pendientes

Antes de implementar la Parte 2 (Ajuste de Saldos), hay que definir cual de estas opciones se toma:

| Opcion | Descripcion | Pros | Contras |
|--------|-------------|------|---------|
| **A: Refactorear pagos** | Modificar el flujo de `registrar-pago` para vincular cada pago a una o mas ventas especificas | Precision total, trazabilidad completa | Cambio mas grande, afecta flujo existente, requiere UI para seleccionar a que venta se aplica el pago |
| **B: Ratio a nivel cliente** | Calcular ratio pendiente sobre el saldo general del cliente en vez de por venta | Sin cambios al flujo actual | Menos preciso cuando hay multiples ventas del mismo cliente |
| **C: Ajuste completo (ratio=1.0)** | Aplicar el ajuste COMPLETO sobre todas las ventas CC pendientes sin considerar pagos parciales | Mas simple, sin cambios al flujo | Puede sobreajustar si el cliente ya pago parcialmente |

**La Parte 1 (Estado de Cuenta PDF) NO tiene este problema y puede implementarse de inmediato.**
