"""Rutas del panel de superadministrador."""

import secrets
import string

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Empresa, Usuario
from ..utils.decorators import superadmin_required

bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')


def _generar_password_temporal(longitud=12):
    """Genera una contraseña aleatoria alfanumérica."""
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(longitud))


def _obtener_admin_principal(empresa_id):
    """Obtiene el primer usuario administrador de una empresa."""
    return (
        Usuario.query.filter_by(empresa_id=empresa_id, rol='administrador')
        .order_by(Usuario.created_at)
        .first()
    )


@bp.route('/')
@login_required
@superadmin_required
def index():
    """Dashboard del superadmin con métricas."""
    total_empresas = Empresa.query.count()
    empresas_pendientes = Empresa.query.filter_by(aprobada=False, activa=True).count()
    empresas_aprobadas = Empresa.query.filter_by(aprobada=True, activa=True).count()
    empresas_inactivas = Empresa.query.filter_by(activa=False).count()

    pendientes = (
        Empresa.query.filter_by(aprobada=False, activa=True)
        .order_by(Empresa.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'superadmin/dashboard.html',
        total_empresas=total_empresas,
        empresas_pendientes=empresas_pendientes,
        empresas_aprobadas=empresas_aprobadas,
        empresas_inactivas=empresas_inactivas,
        pendientes=pendientes,
    )


@bp.route('/empresas')
@login_required
@superadmin_required
def empresas():
    """Listado de todas las empresas con sus admins."""
    filtro = request.args.get('filtro', 'todas')

    query = Empresa.query.order_by(Empresa.created_at.desc())
    if filtro == 'pendientes':
        query = query.filter_by(aprobada=False, activa=True)
    elif filtro == 'aprobadas':
        query = query.filter_by(aprobada=True, activa=True)
    elif filtro == 'inactivas':
        query = query.filter_by(activa=False)

    empresas_list = query.all()

    empresas_con_admin = []
    for emp in empresas_list:
        admin = _obtener_admin_principal(emp.id)
        empresas_con_admin.append({'empresa': emp, 'admin': admin})

    return render_template(
        'superadmin/empresas.html',
        empresas=empresas_con_admin,
        filtro_actual=filtro,
    )


@bp.route('/empresas/<int:empresa_id>/aprobar', methods=['POST'])
@login_required
@superadmin_required
def aprobar_empresa(empresa_id):
    """Aprueba una empresa pendiente."""
    empresa = db.session.get(Empresa, empresa_id)
    if not empresa:
        flash('Empresa no encontrada.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    empresa.aprobada = True
    db.session.commit()
    flash(f'Empresa "{empresa.nombre}" aprobada exitosamente.', 'success')
    return redirect(url_for('superadmin.empresas'))


@bp.route('/empresas/<int:empresa_id>/desactivar-admin', methods=['POST'])
@login_required
@superadmin_required
def desactivar_admin(empresa_id):
    """Desactiva el admin principal de una empresa."""
    admin = _obtener_admin_principal(empresa_id)
    if not admin:
        flash('No se encontró administrador para esta empresa.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    admin.activo = False
    db.session.commit()
    flash(f'Usuario {admin.email} desactivado.', 'success')
    return redirect(url_for('superadmin.empresas'))


@bp.route('/empresas/<int:empresa_id>/activar-admin', methods=['POST'])
@login_required
@superadmin_required
def activar_admin(empresa_id):
    """Reactiva el admin principal de una empresa."""
    admin = _obtener_admin_principal(empresa_id)
    if not admin:
        flash('No se encontró administrador para esta empresa.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    admin.activo = True
    db.session.commit()
    flash(f'Usuario {admin.email} activado.', 'success')
    return redirect(url_for('superadmin.empresas'))


@bp.route('/empresas/<int:empresa_id>/reset-password', methods=['POST'])
@login_required
@superadmin_required
def reset_password(empresa_id):
    """Genera contraseña temporal para el admin de una empresa."""
    admin = _obtener_admin_principal(empresa_id)
    if not admin:
        flash('No se encontró administrador para esta empresa.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    password_temporal = _generar_password_temporal()
    admin.set_password(password_temporal)
    admin.debe_cambiar_password = True
    db.session.commit()

    flash(
        f'Contraseña temporal para {admin.email}: {password_temporal}',
        'info',
    )
    return redirect(url_for('superadmin.empresas'))
