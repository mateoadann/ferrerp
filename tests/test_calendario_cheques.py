"""Tests del calendario de cheques."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from flask import Blueprint
from flask_login import login_user

from app import create_app
from app.extensions import db
from app.models import Banco, Cheque, Empresa, Usuario

# ---------------------------------------------------------------------------
# Helpers (copiados del patrón de test_cheque.py)
# ---------------------------------------------------------------------------


def _crear_empresa_aprobada(nombre='Empresa Calendario'):
    empresa = Empresa(nombre=nombre, activa=True, aprobada=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id, email='cal@ferrerp.test'):
    usuario = Usuario(
        email=email,
        nombre='Usuario Calendario',
        rol='administrador',
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_banco(empresa_id, nombre='Banco Nacion'):
    banco = Banco(nombre=nombre, empresa_id=empresa_id, activo=True)
    db.session.add(banco)
    db.session.flush()
    return banco


def _crear_cheque(empresa_id, usuario_id, **kwargs):
    banco = Banco.query.filter_by(empresa_id=empresa_id).first()
    if not banco:
        banco = _crear_banco(empresa_id)

    datos = {
        'numero_cheque': '00012345',
        'banco_id': banco.id,
        'fecha_emision': date.today(),
        'fecha_vencimiento': date.today() + timedelta(days=30),
        'importe': Decimal('5000.00'),
        'referencia_tipo': 'venta',
        'referencia_id': 1,
        'estado': 'en_cartera',
        'empresa_id': empresa_id,
        'usuario_id': usuario_id,
    }
    datos.update(kwargs)
    cheque = Cheque(**datos)
    db.session.add(cheque)
    db.session.commit()
    return cheque


@pytest.fixture
def app_con_login():
    """App con LOGIN_DISABLED=False para tests de rutas con current_user."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )

    test_bp = Blueprint('test_cal_login', __name__)

    @test_bp.route('/test-login/<int:user_id>')
    def test_login(user_id):
        usuario = db.session.get(Usuario, user_id)
        login_user(usuario)
        return 'logged-in'

    with app.app_context():
        app.register_blueprint(test_bp)
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _login_client(app_con_login, usuario):
    client = app_con_login.test_client()
    client.get(f'/test-login/{usuario.id}')
    return client


# ---------------------------------------------------------------------------
# Tests de renderizado básico
# ---------------------------------------------------------------------------


class TestCalendarioRenderizado:
    """Tests de renderizado básico de la vista calendario."""

    def test_calendario_retorna_200(self, app_con_login):
        """GET /ventas/cheques/calendario retorna 200."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200

    def test_calendario_muestra_tres_meses(self, app_con_login):
        """El calendario muestra 3 meses en la página."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200
        html = resp.data.decode()
        # El template itera 3 meses; cada uno tiene la clase cal-mes-titulo en un div
        # (la definición CSS en el <style> también la contiene, por eso contamos >= 3)
        assert html.count('<div class="cal-mes-titulo">') == 3

    def test_calendario_sin_autenticacion_redirige(self, app_con_login):
        """GET /ventas/cheques/calendario sin login redirige al login."""
        client = app_con_login.test_client()
        resp = client.get('/ventas/cheques/calendario')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Tests de navegación (mes_central)
# ---------------------------------------------------------------------------


class TestCalendarioNavegacion:
    """Tests de navegación por mes_central."""

    def test_mes_central_junio_2026_muestra_mayo_junio_julio(self, app_con_login):
        """GET ?mes_central=2026-06 muestra Mayo, Junio y Julio 2026."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario?mes_central=2026-06')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Mayo' in html
        assert 'Junio' in html
        assert 'Julio' in html

    def test_mes_central_invalido_usa_mes_actual(self, app_con_login):
        """GET ?mes_central=invalido usa el mes actual sin romper."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario?mes_central=invalido')

        assert resp.status_code == 200

    def test_mes_central_enero_muestra_diciembre_anterior(self, app_con_login):
        """?mes_central=2026-01 muestra Diciembre 2025 como mes previo."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario?mes_central=2026-01')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Diciembre' in html
        assert '2025' in html
        assert 'Enero' in html
        assert 'Febrero' in html


# ---------------------------------------------------------------------------
# Tests de filtrado multi-tenant
# ---------------------------------------------------------------------------


class TestCalendarioMultiTenant:
    """Tests de aislamiento por empresa en el calendario."""

    def test_solo_muestra_cheques_de_propia_empresa(self, app_con_login):
        """Cheques de otra empresa no aparecen en el calendario."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario(empresa_a.id, 'a_cal@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        usuario_b = _crear_usuario(empresa_b.id, 'b_cal@test.com')
        db.session.commit()

        # Cheque de empresa B con número único
        hoy = date.today()
        _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            numero_cheque='EMPBCAL001',
            fecha_vencimiento=date(hoy.year, hoy.month, 1),
        )

        client = _login_client(app_con_login, usuario_a)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'EMPBCAL001' not in html


# ---------------------------------------------------------------------------
# Tests de chips por tipo
# ---------------------------------------------------------------------------


class TestCalendarioChips:
    """Tests de que los chips correctos aparecen para cada tipo de cheque."""

    def test_cheque_recibido_aparece_en_calendario(self, app_con_login):
        """Un cheque recibido aparece en el calendario."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='REC_CAL_001',
            fecha_vencimiento=date(hoy.year, hoy.month, 1),
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'chip-recibido' in html

    def test_cheque_emitido_aparece_en_calendario(self, app_con_login):
        """Un cheque emitido aparece en el calendario."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_CAL_001',
            fecha_vencimiento=date(hoy.year, hoy.month, 1),
            destinatario='Proveedor Cal',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'chip-emitido' in html

    def test_mas_de_tres_cheques_muestra_chip_mas(self, app_con_login):
        """Cuando hay más de 3 cheques en un día, aparece el chip '+N más'."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fecha_venc = date(hoy.year, hoy.month, 1)
        for i in range(4):
            _crear_cheque(
                empresa_id=empresa.id,
                usuario_id=usuario.id,
                tipo='recibido',
                numero_cheque=f'MULTI{i:03d}',
                fecha_vencimiento=fecha_venc,
            )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'chip-mas' in html
        assert 'más' in html


# ---------------------------------------------------------------------------
# Tests de helpers internos
# ---------------------------------------------------------------------------


class TestHelpersCalendario:
    """Tests unitarios de las funciones helper del calendario."""

    def test_mes_anterior_enero(self, app):
        """_mes_anterior de enero retorna diciembre del año anterior."""
        from app.routes.ventas import _mes_anterior

        anio, mes = _mes_anterior(2026, 1)
        assert anio == 2025
        assert mes == 12

    def test_mes_siguiente_diciembre(self, app):
        """_mes_siguiente de diciembre retorna enero del año siguiente."""
        from app.routes.ventas import _mes_siguiente

        anio, mes = _mes_siguiente(2025, 12)
        assert anio == 2026
        assert mes == 1

    def test_construir_semanas_tiene_7_columnas(self, app):
        """_construir_semanas siempre retorna semanas de 7 días."""
        from app.routes.ventas import _construir_semanas

        semanas = _construir_semanas(2026, 5)
        for semana in semanas:
            assert len(semana) == 7

    def test_texto_chip_miles(self, app):
        """_texto_chip formatea miles con k."""
        from unittest.mock import MagicMock

        from app.routes.ventas import _texto_chip

        cheque = MagicMock()
        cheque.importe = Decimal('40000')
        assert _texto_chip(cheque) == '$40k'

    def test_texto_chip_millones(self, app):
        """_texto_chip formatea millones con M."""
        from unittest.mock import MagicMock

        from app.routes.ventas import _texto_chip

        cheque = MagicMock()
        cheque.importe = Decimal('2500000')
        assert _texto_chip(cheque) == '$2.5M'

    def test_construir_meses_retorna_tres(self, app):
        """_construir_meses retorna exactamente 3 meses."""
        from app.routes.ventas import _construir_meses

        meses = _construir_meses(2026, 5, {})
        assert len(meses) == 3
        assert meses[0]['mes'] == 4  # abril
        assert meses[1]['mes'] == 5  # mayo
        assert meses[2]['mes'] == 6  # junio
