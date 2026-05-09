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

    def test_mes_central_junio_2026_muestra_junio_julio_agosto(self, app_con_login):
        """GET ?mes_central=2026-06 muestra Junio, Julio y Agosto 2026.

        Ventana asimétrica: el mes central queda a la izquierda y se ven los
        2 meses siguientes. El mes anterior (Mayo) NO se muestra.
        """
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario?mes_central=2026-06')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Junio' in html
        assert 'Julio' in html
        assert 'Agosto' in html
        # El mes anterior NO debe aparecer en los títulos del calendario.
        # Nota: 'Mayo' podría aparecer si está en otro contexto del template,
        # pero no como título de mes del calendario. Verificamos con el patrón
        # del título <div class="cal-mes-titulo">…</div>.
        assert '<div class="cal-mes-titulo">Mayo' not in html

    def test_mes_central_invalido_usa_mes_actual(self, app_con_login):
        """GET ?mes_central=invalido usa el mes actual sin romper."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario?mes_central=invalido')

        assert resp.status_code == 200

    def test_mes_central_enero_no_muestra_diciembre_anterior(self, app_con_login):
        """?mes_central=2026-01 muestra Enero, Febrero y Marzo 2026.

        Con la ventana asimétrica, Diciembre 2025 (mes anterior) ya NO aparece
        como título de mes del calendario.
        """
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario?mes_central=2026-01')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Enero' in html
        assert 'Febrero' in html
        assert 'Marzo' in html
        # Diciembre 2025 (mes anterior) ya no aparece como título de mes
        assert '<div class="cal-mes-titulo">Diciembre' not in html

    def test_mes_central_diciembre_muestra_enero_siguiente(self, app_con_login):
        """?mes_central=2025-12 muestra Diciembre 2025, Enero 2026 y Febrero 2026.

        Edge case del wrap de año: el +1 y +2 cruzan al siguiente año.
        """
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario?mes_central=2025-12')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Diciembre' in html
        assert 'Enero' in html
        assert 'Febrero' in html
        assert '2025' in html
        assert '2026' in html


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
# Tests de recuadros por tipo (totales por día)
# ---------------------------------------------------------------------------


class TestCalendarioRecuadros:
    """Tests de los recuadros con totales que aparecen por día y tipo."""

    def test_cheque_recibido_aparece_en_calendario(self, app_con_login):
        """Un cheque recibido genera un recuadro verde en el calendario."""
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
        assert 'recuadro-recibido' in html

    def test_cheque_emitido_aparece_en_calendario(self, app_con_login):
        """Un cheque emitido genera un recuadro rojo en el calendario."""
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
        assert 'recuadro-emitido' in html

    def test_calendario_muestra_totales_por_dia(self, app_con_login):
        """Cuando hay varios cheques en un día, se muestra el total sumado."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fecha_venc = date(hoy.year, hoy.month, 1)
        for i, importe in enumerate([Decimal('10000'), Decimal('30000')]):
            _crear_cheque(
                empresa_id=empresa.id,
                usuario_id=usuario.id,
                tipo='recibido',
                numero_cheque=f'TOT_REC_{i:03d}',
                fecha_vencimiento=fecha_venc,
                importe=importe,
            )
        for i, importe in enumerate([Decimal('500000'), Decimal('1500000')]):
            _crear_cheque(
                empresa_id=empresa.id,
                usuario_id=usuario.id,
                tipo='emitido',
                numero_cheque=f'TOT_EMI_{i:03d}',
                fecha_vencimiento=fecha_venc,
                destinatario='Proveedor Total',
                importe=importe,
            )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200
        html = resp.data.decode()
        # Total recibidos = $40.000 → '$40k' en formato compacto
        assert '$40k' in html
        # Total emitidos = $2.000.000 → '$2.0M'
        assert '$2.0M' in html
        # Cantidad por tipo: 2 y 2
        assert 'recuadro-recibido' in html
        assert 'recuadro-emitido' in html

    def test_dia_sin_cheques_no_muestra_recuadros(self, app_con_login):
        """Días sin cheques no deben mostrar recuadros."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/calendario')

        assert resp.status_code == 200
        html = resp.data.decode()
        # Sin cheques, no hay recuadros (el string aparece solo en CSS y leyenda)
        # El conteo en CSS es 1 ocurrencia de cada (definición) + 1 en leyenda = 2
        # Si hubiera datos, aparecería más veces.
        assert html.count('recuadro-recibido') <= 2
        assert html.count('recuadro-emitido') <= 2


# ---------------------------------------------------------------------------
# Tests de filtro por banco
# ---------------------------------------------------------------------------


class TestCalendarioFiltroBanco:
    """Tests del filtro por banco (solo afecta a cheques emitidos)."""

    def test_filtro_banco_solo_afecta_emitidos(self, app_con_login):
        """Al filtrar por banco, los emitidos de otros bancos NO aparecen pero los recibidos sí."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        banco_a = _crear_banco(empresa.id, nombre='Banco A')
        banco_b = _crear_banco(empresa.id, nombre='Banco B')
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 5)

        # Emitido banco A: importe alto bien identificable
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_BA',
            banco_id=banco_a.id,
            fecha_vencimiento=fv,
            importe=Decimal('1500000'),
            destinatario='Prov A',
        )
        # Emitido banco B: importe distinto
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_BB',
            banco_id=banco_b.id,
            fecha_vencimiento=fv,
            importe=Decimal('80000'),
            destinatario='Prov B',
        )
        # Recibido (sin banco): importe distinto
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='REC_X',
            banco_id=None,
            fecha_vencimiento=fv,
            importe=Decimal('25000'),
        )

        client = _login_client(app_con_login, usuario)

        # Sin filtro: ambos emitidos aparecen sumados ($1.500.000 + $80.000 = $1.580.000 → '$2M')
        resp_sin = client.get(
            f'/ventas/cheques/calendario?mes_central={hoy.year:04d}-{hoy.month:02d}'
        )
        assert resp_sin.status_code == 200
        html_sin = resp_sin.data.decode()
        # Recibido: $25k
        assert '$25k' in html_sin

        # Con filtro banco_a: emitidos suman solo $1.500.000 → '$1.5M' (no $2M)
        resp_a = client.get(
            f'/ventas/cheques/calendario?mes_central={hoy.year:04d}-{hoy.month:02d}'
            f'&banco_id={banco_a.id}'
        )
        assert resp_a.status_code == 200
        html_a = resp_a.data.decode()
        assert '$1.5M' in html_a
        # Recibidos siguen apareciendo (no se filtran por banco)
        assert '$25k' in html_a

        # Con filtro banco_b: emitidos suman $80.000 → '$80k'
        resp_b = client.get(
            f'/ventas/cheques/calendario?mes_central={hoy.year:04d}-{hoy.month:02d}'
            f'&banco_id={banco_b.id}'
        )
        assert resp_b.status_code == 200
        html_b = resp_b.data.decode()
        assert '$80k' in html_b
        # Recibidos siguen apareciendo
        assert '$25k' in html_b


# ---------------------------------------------------------------------------
# Tests del sidenav (endpoint /cheques/calendario/dia)
# ---------------------------------------------------------------------------


class TestCalendarioSidenavDia:
    """Tests del partial del sidenav con detalle de cheques de un día."""

    def test_sidenav_dia_recibidos(self, app_con_login):
        """GET /ventas/cheques/calendario/dia con tipo=recibido devuelve la lista."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 8)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='SIDE_REC',
            fecha_vencimiento=fv,
            importe=Decimal('15000'),
        )
        # Otro cheque emitido el mismo día (no debe aparecer)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='SIDE_EMI',
            fecha_vencimiento=fv,
            destinatario='Otro',
            importe=Decimal('99999'),
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}&tipo=recibido'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'SIDE_REC' in html
        assert 'SIDE_EMI' not in html
        # Header con tipo recibidos
        assert 'recibidos' in html.lower()

    def test_sidenav_dia_emitidos_filtra_por_banco(self, app_con_login):
        """GET con tipo=emitido y banco_id solo trae emitidos de ese banco."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        banco_a = _crear_banco(empresa.id, nombre='Banco A Side')
        banco_b = _crear_banco(empresa.id, nombre='Banco B Side')
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 9)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_A_SIDE',
            banco_id=banco_a.id,
            fecha_vencimiento=fv,
            destinatario='Prov A',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_B_SIDE',
            banco_id=banco_b.id,
            fecha_vencimiento=fv,
            destinatario='Prov B',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}&tipo=emitido'
            f'&banco_id={banco_a.id}'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'EMI_A_SIDE' in html
        assert 'EMI_B_SIDE' not in html

    def test_sidenav_dia_tipo_invalido_400(self, app_con_login):
        """Tipo inválido retorna 400."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        hoy = date.today()
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={hoy.isoformat()}&tipo=foo'
        )
        assert resp.status_code == 400

    def test_sidenav_dia_fecha_invalida_400(self, app_con_login):
        """Fecha inválida retorna 400."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            '/ventas/cheques/calendario/dia?fecha=no-es-fecha&tipo=recibido'
        )
        assert resp.status_code == 400

    def test_sidenav_dia_sin_cheques_muestra_mensaje(self, app_con_login):
        """Día sin cheques muestra el mensaje 'No hay cheques'."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        hoy = date.today()
        # Fecha lejana sin cheques
        fecha_lejana = date(hoy.year, hoy.month, 28)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fecha_lejana.isoformat()}'
            '&tipo=recibido'
        )
        assert resp.status_code == 200
        assert 'No hay cheques' in resp.data.decode()

    def test_sidenav_recibido_muestra_boton_cambiar_estado(
        self, app_con_login
    ):
        """Cheque recibido en estado 'en_cartera' debe mostrar botón
        'Cambiar estado' apuntando al modal de acciones."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 18)
        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='REC_BTN',
            fecha_vencimiento=fv,
            estado='en_cartera',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}'
            '&tipo=recibido'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'REC_BTN' in html
        # El botón "Cambiar estado" debe estar presente.
        assert 'Cambiar estado' in html
        # Y debe apuntar al endpoint de acciones con desde_calendario=1.
        assert (
            f'/ventas/cheques/{cheque.id}/acciones?desde_calendario=1' in html
        )

    def test_sidenav_emitido_muestra_boton_cambiar_estado(
        self, app_con_login
    ):
        """REGRESIÓN: cheque emitido vivo debe mostrar botón 'Cambiar estado'
        en el sidenav, igual que los recibidos. Cubre los dos nombres del
        estado vivo: 'en_cartera' (rama 039 sola) y 'emitido' (post-merge
        con feature/036)."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 19)

        # Caso A: emitido con estado='emitido' (post-rename de feature/036).
        cheque_nuevo = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_BTN_NEW',
            fecha_vencimiento=fv,
            destinatario='Prov A',
            estado='emitido',
        )
        # Caso B: emitido con estado='en_cartera' (rama 039 sola).
        cheque_viejo = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_BTN_OLD',
            fecha_vencimiento=fv,
            destinatario='Prov B',
            estado='en_cartera',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}'
            '&tipo=emitido'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        # Ambos emitidos deben aparecer.
        assert 'EMI_BTN_NEW' in html
        assert 'EMI_BTN_OLD' in html
        # Y AMBOS deben mostrar el botón "Cambiar estado". Antes del fix,
        # el sidenav lo escondía cuando estado != 'en_cartera'.
        assert html.count('Cambiar estado') == 2
        # Cada uno apunta a su propio endpoint de acciones.
        assert (
            f'/ventas/cheques/{cheque_nuevo.id}/acciones?desde_calendario=1'
            in html
        )
        assert (
            f'/ventas/cheques/{cheque_viejo.id}/acciones?desde_calendario=1'
            in html
        )

    def test_sidenav_muestra_badge_echeq(self, app_con_login):
        """Cheque con tipo_cheque='echeq' debe mostrar el badge 'Echeq' en
        el sidenav (incluye el partial _badge_echeq.html)."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 20)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='REC_ECHEQ',
            fecha_vencimiento=fv,
            tipo_cheque='echeq',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}'
            '&tipo=recibido'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'REC_ECHEQ' in html
        # El badge debe estar presente.
        assert 'badge-echeq' in html
        assert 'Echeq' in html

    def test_sidenav_no_muestra_badge_si_cheque_fisico(self, app_con_login):
        """Cheque con tipo_cheque='cheque' (default, fisico) NO debe mostrar
        el badge: la ausencia ya es la indicacion visual."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 21)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='REC_FISICO',
            fecha_vencimiento=fv,
            tipo_cheque='cheque',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}'
            '&tipo=recibido'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'REC_FISICO' in html
        # El badge NO debe estar.
        assert 'badge-echeq' not in html


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

    def test_formatear_monto_compacto_miles(self, app):
        """_formatear_monto_compacto formatea miles con k."""
        from app.routes.ventas import _formatear_monto_compacto

        assert _formatear_monto_compacto(Decimal('40000')) == '$40k'

    def test_formatear_monto_compacto_millones(self, app):
        """_formatear_monto_compacto formatea millones con M."""
        from app.routes.ventas import _formatear_monto_compacto

        assert _formatear_monto_compacto(Decimal('2500000')) == '$2.5M'

    def test_formatear_monto_compacto_pequenio(self, app):
        """_formatear_monto_compacto formatea valores chicos sin sufijo."""
        from app.routes.ventas import _formatear_monto_compacto

        assert _formatear_monto_compacto(Decimal('500')) == '$500'

    def test_formatear_monto_compacto_cero(self, app):
        """_formatear_monto_compacto maneja cero sin romper."""
        from app.routes.ventas import _formatear_monto_compacto

        assert _formatear_monto_compacto(Decimal('0')) == '$0'

    def test_construir_meses_retorna_tres(self, app):
        """_construir_meses retorna exactamente 3 meses (ventana asimétrica)."""
        from app.routes.ventas import _construir_meses

        meses = _construir_meses(2026, 5, {})
        assert len(meses) == 3
        # Ventana asimétrica: [central, central+1, central+2]
        assert meses[0]['mes'] == 5  # mayo (central)
        assert meses[1]['mes'] == 6  # junio
        assert meses[2]['mes'] == 7  # julio

    def test_construir_meses_wrap_diciembre(self, app):
        """_construir_meses maneja el wrap de año cuando central=diciembre."""
        from app.routes.ventas import _construir_meses

        meses = _construir_meses(2025, 12, {})
        assert len(meses) == 3
        assert meses[0]['mes'] == 12 and meses[0]['anio'] == 2025
        assert meses[1]['mes'] == 1 and meses[1]['anio'] == 2026
        assert meses[2]['mes'] == 2 and meses[2]['anio'] == 2026

    def test_agrupar_cheques_suma_totales(self, app):
        """_agrupar_cheques_por_dia suma importes por fecha y tipo."""
        from unittest.mock import MagicMock

        from app.routes.ventas import _agrupar_cheques_por_dia

        fv = date(2026, 5, 10)
        c1 = MagicMock()
        c1.fecha_vencimiento = fv
        c1.tipo = 'recibido'
        c1.importe = Decimal('1000')
        c2 = MagicMock()
        c2.fecha_vencimiento = fv
        c2.tipo = 'recibido'
        c2.importe = Decimal('500')
        c3 = MagicMock()
        c3.fecha_vencimiento = fv
        c3.tipo = 'emitido'
        c3.importe = Decimal('2000')

        resultado = _agrupar_cheques_por_dia([c1, c2, c3])
        assert resultado[fv]['recibidos']['total'] == Decimal('1500')
        assert resultado[fv]['recibidos']['cantidad'] == 2
        assert resultado[fv]['emitidos']['total'] == Decimal('2000')
        assert resultado[fv]['emitidos']['cantidad'] == 1


# ---------------------------------------------------------------------------
# Tests de filtro por estado (solo en_cartera)
# ---------------------------------------------------------------------------


class TestCalendarioFiltroEstado:
    """El calendario y el sidenav SOLO muestran cheques con estado en_cartera.

    Los cheques cobrados/endosados/sin_fondos ya no son del usuario (ya los
    entregó/pagó/cobró), por lo que no deben sumarse en los totales del día
    ni aparecer en el detalle del sidenav.
    """

    def test_calendario_excluye_cheques_no_en_cartera(self, app_con_login):
        """En el calendario, solo se suma el cheque en_cartera; los demás
        estados (cobrado, endosado, sin_fondos) quedan fuera del total."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 12)

        # Único en_cartera: $40.000 → '$40k' en formato compacto
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='ESTADO_OK',
            fecha_vencimiento=fv,
            importe=Decimal('40000'),
            estado='en_cartera',
        )
        # Otros estados con importes muy altos: si se sumaran, el total
        # explotaría a millones. No deben aparecer.
        for estado, num in [
            ('cobrado', 'ESTADO_COB'),
            ('endosado', 'ESTADO_END'),
            ('sin_fondos', 'ESTADO_SIN'),
        ]:
            _crear_cheque(
                empresa_id=empresa.id,
                usuario_id=usuario.id,
                tipo='recibido',
                numero_cheque=num,
                fecha_vencimiento=fv,
                importe=Decimal('9000000'),
                estado=estado,
            )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario?mes_central={hoy.year:04d}-{hoy.month:02d}'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        # Solo el en_cartera suma: $40k
        assert '$40k' in html
        # Los $9M de los otros estados NO deben aparecer
        assert '$9.0M' not in html
        assert '$27.0M' not in html  # tampoco la suma de los tres

    def test_sidenav_excluye_cheques_no_en_cartera(self, app_con_login):
        """En el sidenav del día, solo aparecen cheques en_cartera. Los
        cobrados, endosados y sin_fondos quedan ocultos."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 14)

        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='SIDE_CART',
            fecha_vencimiento=fv,
            estado='en_cartera',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='SIDE_COB',
            fecha_vencimiento=fv,
            estado='cobrado',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='SIDE_END',
            fecha_vencimiento=fv,
            estado='endosado',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            numero_cheque='SIDE_SIN',
            fecha_vencimiento=fv,
            estado='sin_fondos',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}&tipo=recibido'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'SIDE_CART' in html
        assert 'SIDE_COB' not in html
        assert 'SIDE_END' not in html
        assert 'SIDE_SIN' not in html

    def test_calendario_incluye_emitidos_estado_emitido(self, app_con_login):
        """Cheques EMITIDOS con estado='emitido' (post-rename de feature/036)
        deben sumar en el total del día del calendario.

        Filtro defensivo: para sobrevivir al merge con feature/036 (que
        renombra el estado vivo de cheques emitidos de 'en_cartera' a
        'emitido'), el calendario acepta ambos estados para tipo='emitido'.
        """
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 16)

        # Cheque emitido con el nuevo estado vivo 'emitido' (post feature/036).
        # Importe identificable: $250.000 → '$250k' compacto.
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='EMI_NEW_STATE',
            fecha_vencimiento=fv,
            destinatario='Proveedor Post-036',
            importe=Decimal('250000'),
            estado='emitido',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario?mes_central={hoy.year:04d}-{hoy.month:02d}'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        # El emitido en estado 'emitido' debe sumar en el total del día.
        assert '$250k' in html
        # Y debe aparecer un recuadro emitido (no quedar invisible).
        assert 'recuadro-emitido' in html

    def test_sidenav_incluye_emitidos_estado_emitido(self, app_con_login):
        """El sidenav del día con tipo=emitido también acepta estado='emitido'
        (filtro defensivo para post-rename de feature/036)."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        hoy = date.today()
        fv = date(hoy.year, hoy.month, 17)

        # Cheque emitido con el nuevo estado vivo 'emitido' (post feature/036).
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='SIDE_EMI_NEW',
            fecha_vencimiento=fv,
            destinatario='Proveedor Post-036',
            importe=Decimal('33000'),
            estado='emitido',
        )
        # También un emitido en 'en_cartera' (rama 039 sola): debe seguir
        # apareciendo. No queremos romper ese caso.
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            numero_cheque='SIDE_EMI_OLD',
            fecha_vencimiento=fv,
            destinatario='Proveedor Pre-036',
            importe=Decimal('44000'),
            estado='en_cartera',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            f'/ventas/cheques/calendario/dia?fecha={fv.isoformat()}&tipo=emitido'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        # Ambos emitidos deben aparecer (defensa anti-rename funciona).
        assert 'SIDE_EMI_NEW' in html
        assert 'SIDE_EMI_OLD' in html
