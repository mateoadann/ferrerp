"""Rutas de proveedores."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from ..extensions import db
from ..models import Proveedor, OrdenCompra
from ..forms.proveedor_forms import ProveedorForm
from ..utils.helpers import paginar_query, es_peticion_htmx

bp = Blueprint('proveedores', __name__, url_prefix='/proveedores')


@bp.route('/')
@login_required
def index():
    """Listado de proveedores."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')
    solo_activos = request.args.get('activos', '1') == '1'

    query = Proveedor.query

    if busqueda:
        query = query.filter(
            db.or_(
                Proveedor.nombre.ilike(f'%{busqueda}%'),
                Proveedor.razon_social.ilike(f'%{busqueda}%'),
                Proveedor.cuit.ilike(f'%{busqueda}%')
            )
        )

    if solo_activos:
        query = query.filter(Proveedor.activo == True)

    query = query.order_by(Proveedor.nombre)
    proveedores = paginar_query(query, page)

    if es_peticion_htmx():
        return render_template(
            'proveedores/_tabla.html',
            proveedores=proveedores,
            busqueda=busqueda
        )

    return render_template(
        'proveedores/index.html',
        proveedores=proveedores,
        busqueda=busqueda,
        solo_activos=solo_activos
    )


@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    """Crear nuevo proveedor."""
    form = ProveedorForm()

    if form.validate_on_submit():
        proveedor = Proveedor(
            nombre=form.nombre.data,
            razon_social=form.razon_social.data,
            cuit=form.cuit.data,
            telefono=form.telefono.data,
            email=form.email.data,
            direccion=form.direccion.data,
            condicion_pago=form.condicion_pago.data,
            notas=form.notas.data,
            activo=form.activo.data
        )

        db.session.add(proveedor)
        db.session.commit()

        flash(f'Proveedor "{proveedor.nombre}" creado correctamente.', 'success')
        return redirect(url_for('proveedores.index'))

    return render_template('proveedores/form.html', form=form, titulo='Nuevo Proveedor')


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de proveedor con historial de compras."""
    proveedor = Proveedor.query.get_or_404(id)

    # Últimas órdenes de compra
    ordenes = OrdenCompra.query.filter_by(
        proveedor_id=id
    ).order_by(
        OrdenCompra.fecha.desc()
    ).limit(10).all()

    return render_template(
        'proveedores/detalle.html',
        proveedor=proveedor,
        ordenes=ordenes
    )


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Editar proveedor."""
    proveedor = Proveedor.query.get_or_404(id)
    form = ProveedorForm(obj=proveedor)

    if form.validate_on_submit():
        proveedor.nombre = form.nombre.data
        proveedor.razon_social = form.razon_social.data
        proveedor.cuit = form.cuit.data
        proveedor.telefono = form.telefono.data
        proveedor.email = form.email.data
        proveedor.direccion = form.direccion.data
        proveedor.condicion_pago = form.condicion_pago.data
        proveedor.notas = form.notas.data
        proveedor.activo = form.activo.data

        db.session.commit()

        flash(f'Proveedor "{proveedor.nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('proveedores.index'))

    return render_template(
        'proveedores/form.html',
        form=form,
        titulo='Editar Proveedor',
        proveedor=proveedor
    )


@bp.route('/<int:id>/toggle-activo', methods=['POST'])
@login_required
def toggle_activo(id):
    """Activar/desactivar proveedor."""
    proveedor = Proveedor.query.get_or_404(id)
    proveedor.activo = not proveedor.activo
    db.session.commit()

    estado = 'activado' if proveedor.activo else 'desactivado'
    flash(f'Proveedor "{proveedor.nombre}" {estado}.', 'success')

    if es_peticion_htmx():
        return '', 204

    return redirect(url_for('proveedores.index'))
