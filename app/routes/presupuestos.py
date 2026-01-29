"""Rutas de presupuestos."""

import json
from datetime import datetime
from decimal import Decimal
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, jsonify, make_response
)
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Presupuesto, Producto, Cliente, Caja, Configuracion
from ..forms.presupuesto_forms import PresupuestoForm, ConvertirPresupuestoForm
from ..utils.helpers import paginar_query, es_peticion_htmx
from ..utils.decorators import admin_required, caja_abierta_required
from ..services import presupuesto_service

bp = Blueprint('presupuestos', __name__, url_prefix='/presupuestos')


@bp.before_request
def _marcar_vencidos():
    """Marca presupuestos vencidos antes de cada request."""
    presupuesto_service.marcar_vencidos()


# ─── Listado ─────────────────────────────────────────────────────────

@bp.route('/')
@login_required
def index():
    """Listado de presupuestos con filtros."""
    page = request.args.get('page', 1, type=int)
    estado = request.args.get('estado', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    busqueda = request.args.get('q', '')

    query = Presupuesto.query

    if estado:
        query = query.filter(Presupuesto.estado == estado)

    if fecha_desde:
        fd = datetime.strptime(fecha_desde, '%Y-%m-%d')
        query = query.filter(Presupuesto.fecha >= fd)

    if fecha_hasta:
        fh = datetime.strptime(fecha_hasta, '%Y-%m-%d')
        fh = fh.replace(hour=23, minute=59, second=59)
        query = query.filter(Presupuesto.fecha <= fh)

    if busqueda:
        query = query.filter(
            db.or_(
                Presupuesto.cliente_nombre.ilike(f'%{busqueda}%'),
                Presupuesto.numero.cast(db.String).ilike(f'%{busqueda}%')
            )
        )
        # También buscar por nombre de cliente registrado
        clientes_ids = [c.id for c in Cliente.query.filter(
            Cliente.nombre.ilike(f'%{busqueda}%')
        ).all()]
        if clientes_ids:
            query = Presupuesto.query.filter(
                db.or_(
                    Presupuesto.cliente_nombre.ilike(f'%{busqueda}%'),
                    Presupuesto.numero.cast(db.String).ilike(f'%{busqueda}%'),
                    Presupuesto.cliente_id.in_(clientes_ids)
                )
            )
            if estado:
                query = query.filter(Presupuesto.estado == estado)
            if fecha_desde:
                query = query.filter(Presupuesto.fecha >= fd)
            if fecha_hasta:
                query = query.filter(Presupuesto.fecha <= fh)

    query = query.order_by(Presupuesto.fecha.desc())
    presupuestos = paginar_query(query, page)

    if es_peticion_htmx():
        return render_template(
            'presupuestos/_tabla.html',
            presupuestos=presupuestos
        )

    return render_template(
        'presupuestos/index.html',
        presupuestos=presupuestos,
        estado_filtro=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        busqueda=busqueda
    )


# ─── Crear ───────────────────────────────────────────────────────────

@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    """Crear nuevo presupuesto."""
    form = PresupuestoForm()

    if request.method == 'POST':
        try:
            cliente_id = request.form.get('cliente_id', 0, type=int)
            cliente_nombre = request.form.get('cliente_nombre', '').strip()
            cliente_telefono = request.form.get('cliente_telefono', '').strip()
            descuento_porcentaje = Decimal(request.form.get('descuento_porcentaje', '0'))
            validez_dias = request.form.get('validez_dias', 15, type=int)
            notas = request.form.get('notas', '').strip()
            items_json = request.form.get('items_json', '[]')

            items = json.loads(items_json)

            if not items:
                flash('Agrega al menos un producto al presupuesto.', 'danger')
                return redirect(url_for('presupuestos.nuevo'))

            presupuesto = presupuesto_service.crear_presupuesto(
                items=items,
                usuario_id=current_user.id,
                cliente_id=cliente_id if cliente_id else None,
                cliente_nombre=cliente_nombre or None,
                cliente_telefono=cliente_telefono or None,
                descuento_porcentaje=descuento_porcentaje,
                validez_dias=validez_dias,
                notas=notas or None
            )

            flash(
                f'Presupuesto #{presupuesto.numero_completo} creado. '
                f'Total: ${presupuesto.total:,.2f}',
                'success'
            )
            return redirect(url_for('presupuestos.detalle', id=presupuesto.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear presupuesto: {str(e)}', 'danger')
            return redirect(url_for('presupuestos.nuevo'))

    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    validez_default = Configuracion.get('presupuesto_validez_dias', 15)

    return render_template(
        'presupuestos/crear.html',
        form=form,
        clientes=clientes,
        validez_default=validez_default
    )


# ─── Detalle ─────────────────────────────────────────────────────────

@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de presupuesto."""
    presupuesto = Presupuesto.query.get_or_404(id)
    form_convertir = ConvertirPresupuestoForm()

    return render_template(
        'presupuestos/detalle.html',
        presupuesto=presupuesto,
        form_convertir=form_convertir
    )


# ─── Editar ──────────────────────────────────────────────────────────

@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Editar presupuesto pendiente."""
    presupuesto = Presupuesto.query.get_or_404(id)

    if not presupuesto.puede_editar:
        flash('Este presupuesto no puede editarse.', 'warning')
        return redirect(url_for('presupuestos.detalle', id=id))

    if request.method == 'POST':
        try:
            cliente_id = request.form.get('cliente_id', 0, type=int)
            cliente_nombre = request.form.get('cliente_nombre', '').strip()
            cliente_telefono = request.form.get('cliente_telefono', '').strip()
            descuento_porcentaje = Decimal(request.form.get('descuento_porcentaje', '0'))
            validez_dias = request.form.get('validez_dias', 15, type=int)
            notas = request.form.get('notas', '').strip()
            items_json = request.form.get('items_json', '[]')

            items = json.loads(items_json)

            if not items:
                flash('Agrega al menos un producto al presupuesto.', 'danger')
                return redirect(url_for('presupuestos.editar', id=id))

            presupuesto_service.actualizar_presupuesto(
                presupuesto=presupuesto,
                items=items,
                cliente_id=cliente_id if cliente_id else None,
                cliente_nombre=cliente_nombre or None,
                cliente_telefono=cliente_telefono or None,
                descuento_porcentaje=descuento_porcentaje,
                validez_dias=validez_dias,
                notas=notas or None
            )

            flash(f'Presupuesto #{presupuesto.numero_completo} actualizado.', 'success')
            return redirect(url_for('presupuestos.detalle', id=id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')
            return redirect(url_for('presupuestos.editar', id=id))

    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    detalles = list(presupuesto.detalles)

    # Preparar items existentes como JSON para Alpine.js
    items_existentes = []
    for d in detalles:
        items_existentes.append({
            'producto_id': d.producto_id,
            'codigo': d.producto.codigo,
            'nombre': d.producto.nombre,
            'cantidad': float(d.cantidad),
            'precio_unitario': float(d.precio_unitario),
            'stock_disponible': float(d.producto.stock_actual)
        })

    validez_dias = (presupuesto.fecha_vencimiento - presupuesto.fecha).days

    return render_template(
        'presupuestos/crear.html',
        form=PresupuestoForm(obj=presupuesto),
        clientes=clientes,
        presupuesto=presupuesto,
        items_existentes=json.dumps(items_existentes),
        validez_dias=validez_dias,
        validez_default=validez_dias,
        editando=True
    )


# ─── Eliminar ────────────────────────────────────────────────────────

@bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    """Eliminar presupuesto (solo admin)."""
    presupuesto = Presupuesto.query.get_or_404(id)
    numero = presupuesto.numero_completo

    db.session.delete(presupuesto)
    db.session.commit()

    flash(f'Presupuesto #{numero} eliminado.', 'success')
    return redirect(url_for('presupuestos.index'))


# ─── Cambios de estado ───────────────────────────────────────────────

@bp.route('/<int:id>/aceptar', methods=['POST'])
@login_required
def aceptar(id):
    """Marcar presupuesto como aceptado."""
    presupuesto = Presupuesto.query.get_or_404(id)

    try:
        presupuesto_service.cambiar_estado(presupuesto, 'aceptado')
        flash(f'Presupuesto #{presupuesto.numero_completo} marcado como aceptado.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('presupuestos.detalle', id=id))


@bp.route('/<int:id>/rechazar', methods=['POST'])
@login_required
def rechazar(id):
    """Marcar presupuesto como rechazado."""
    presupuesto = Presupuesto.query.get_or_404(id)

    try:
        presupuesto_service.cambiar_estado(presupuesto, 'rechazado')
        flash(f'Presupuesto #{presupuesto.numero_completo} marcado como rechazado.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('presupuestos.detalle', id=id))


@bp.route('/<int:id>/convertir', methods=['POST'])
@login_required
@caja_abierta_required
def convertir(id):
    """Convertir presupuesto aceptado en venta."""
    presupuesto = Presupuesto.query.get_or_404(id)
    form = ConvertirPresupuestoForm()

    if form.validate_on_submit():
        try:
            caja = Caja.query.filter_by(estado='abierta').first()

            venta = presupuesto_service.convertir_a_venta(
                presupuesto=presupuesto,
                usuario_id=current_user.id,
                forma_pago=form.forma_pago.data,
                caja_id=caja.id
            )

            flash(
                f'Presupuesto #{presupuesto.numero_completo} convertido a '
                f'Venta #{venta.numero_completo}. Total: ${venta.total:,.2f}',
                'success'
            )
            return redirect(url_for('ventas.detalle', id=venta.id))

        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al convertir: {str(e)}', 'danger')

    return redirect(url_for('presupuestos.detalle', id=id))


# ─── PDF ─────────────────────────────────────────────────────────────

@bp.route('/<int:id>/pdf')
@login_required
def pdf(id):
    """Descargar PDF del presupuesto (autenticado)."""
    presupuesto = Presupuesto.query.get_or_404(id)

    pdf_bytes = presupuesto_service.generar_pdf(presupuesto)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = (
        f'inline; filename=presupuesto_{presupuesto.numero_completo}.pdf'
    )
    return response


@bp.route('/p/<token>')
def pdf_publico(token):
    """Acceso público al PDF del presupuesto via token."""
    presupuesto = Presupuesto.query.filter_by(token=token).first_or_404()

    pdf_bytes = presupuesto_service.generar_pdf(presupuesto)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = (
        f'inline; filename=presupuesto_{presupuesto.numero_completo}.pdf'
    )
    return response


# ─── WhatsApp ────────────────────────────────────────────────────────

@bp.route('/<int:id>/whatsapp')
@login_required
def whatsapp(id):
    """Redirigir a WhatsApp con mensaje y link al PDF."""
    presupuesto = Presupuesto.query.get_or_404(id)

    base_url = request.host_url.rstrip('/')
    telefono = request.args.get('telefono', '')

    url = presupuesto_service.generar_url_whatsapp(
        presupuesto=presupuesto,
        base_url=base_url,
        telefono=telefono or None
    )

    return redirect(url)


# ─── Búsqueda de productos ──────────────────────────────────────────

@bp.route('/buscar-producto')
@login_required
def buscar_producto():
    """Búsqueda de productos para agregar al presupuesto."""
    q = request.args.get('q', '')

    if len(q) < 2:
        return render_template('presupuestos/_resultados_busqueda.html', productos=[])

    productos = Producto.query.filter(
        Producto.activo == True,
        db.or_(
            Producto.codigo.ilike(f'%{q}%'),
            Producto.nombre.ilike(f'%{q}%'),
            Producto.codigo_barras.ilike(f'%{q}%')
        )
    ).limit(10).all()

    return render_template('presupuestos/_resultados_busqueda.html', productos=productos)


@bp.route('/api/producto/<int:id>')
@login_required
def api_producto(id):
    """API para obtener datos de producto."""
    producto = Producto.query.get_or_404(id)
    return jsonify(producto.to_dict())
