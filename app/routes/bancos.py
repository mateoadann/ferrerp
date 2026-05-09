"""Rutas de gestión de bancos."""

from flask import Blueprint, flash, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.banco_forms import BancoForm
from ..models.banco import Banco
from ..utils.decorators import empresa_aprobada_required
from ..utils.helpers import es_peticion_htmx

bp = Blueprint('bancos', __name__, url_prefix='/ventas/cheques/bancos')


@bp.route('/')
@login_required
@empresa_aprobada_required
def index():
    """Listado de bancos de la empresa."""
    bancos = (
        Banco.query_empresa()
        .order_by(Banco.nombre)
        .all()
    )
    form = BancoForm()

    if es_peticion_htmx():
        return render_template(
            'ventas/bancos/_lista_bancos.html',
            bancos=bancos,
            form=form,
        )

    return render_template(
        'ventas/bancos/index.html',
        bancos=bancos,
        form=form,
    )


@bp.route('/json')
@login_required
@empresa_aprobada_required
def listar_json():
    """Retorna bancos activos en formato JSON para selects del POS."""
    bancos = (
        Banco.query_empresa()
        .filter(Banco.activo.is_(True))
        .order_by(Banco.nombre)
        .all()
    )
    return jsonify([{'id': b.id, 'nombre': b.nombre} for b in bancos])


@bp.route('/', methods=['POST'])
@login_required
@empresa_aprobada_required
def crear():
    """Crear un banco nuevo."""
    form = BancoForm()

    if form.validate_on_submit():
        nombre = form.nombre.data.strip().title()

        # Verificar unicidad por empresa
        existente = Banco.query.filter_by(
            empresa_id=current_user.empresa_id,
            nombre=nombre,
        ).first()
        if existente:
            flash(
                f'Ya existe un banco con el nombre "{nombre}".',
                'danger',
            )
            return redirect(url_for('bancos.index'))

        banco = Banco(
            nombre=nombre,
            activo=form.activo.data,
            empresa_id=current_user.empresa_id,
        )
        db.session.add(banco)
        db.session.commit()

        flash(f'Banco "{banco.nombre}" creado correctamente.', 'success')
        return redirect(url_for('bancos.index'))

    for campo, errores in form.errors.items():
        for error in errores:
            flash(error, 'danger')

    return redirect(url_for('bancos.index'))


@bp.route('/<int:id>/editar', methods=['POST'])
@login_required
@empresa_aprobada_required
def editar(id):
    """Editar un banco existente."""
    banco = Banco.get_o_404(id)
    form = BancoForm()

    if form.validate_on_submit():
        nombre = form.nombre.data.strip().title()

        # Verificar unicidad (excluyendo el banco actual)
        existente = Banco.query.filter(
            Banco.empresa_id == current_user.empresa_id,
            Banco.nombre == nombre,
            Banco.id != banco.id,
        ).first()
        if existente:
            flash(
                f'Ya existe un banco con el nombre "{nombre}".',
                'danger',
            )
            return redirect(url_for('bancos.index'))

        banco.nombre = nombre
        banco.activo = form.activo.data
        db.session.commit()

        flash(f'Banco "{banco.nombre}" actualizado.', 'success')
        return redirect(url_for('bancos.index'))

    for campo, errores in form.errors.items():
        for error in errores:
            flash(error, 'danger')

    return redirect(url_for('bancos.index'))


@bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@empresa_aprobada_required
def eliminar(id):
    """Eliminar un banco (soft delete si tiene cheques, hard delete si no)."""
    banco = Banco.get_o_404(id)

    # Verificar si tiene cheques asociados
    tiene_cheques = banco.cheques.count() > 0

    if tiene_cheques:
        banco.activo = False
        db.session.commit()
        flash(
            f'Banco "{banco.nombre}" desactivado '
            f'(tiene cheques asociados).',
            'warning',
        )
    else:
        nombre = banco.nombre
        db.session.delete(banco)
        db.session.commit()
        flash(f'Banco "{nombre}" eliminado.', 'success')

    return redirect(url_for('bancos.index'))
