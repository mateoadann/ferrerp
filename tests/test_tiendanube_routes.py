"""Tests para las rutas de integración con Tienda Nube."""

import hashlib
import hmac
import json

from app.extensions import db
from app.models import Empresa, SyncLog, TiendaNubeCredencial, Usuario

# -------------------------------------------------------------------
# Helpers de test
# -------------------------------------------------------------------


def _crear_empresa():
    """Crea una empresa de prueba."""
    empresa = Empresa(nombre='Ferretería Test', activa=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id, email='tn-route@ferrerp.test'):
    """Crea un usuario admin de prueba."""
    usuario = Usuario(
        email=email,
        nombre='Admin TN',
        rol='administrador',
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_credencial(empresa_id, tienda_id='12345', app_secret='secret_test_456'):
    """Crea una credencial TN activa de prueba."""
    cred = TiendaNubeCredencial(
        empresa_id=empresa_id,
        tn_app_id='app_test_123',
        tn_app_secret=app_secret,
        tienda_id_externo=tienda_id,
        usuario_id_externo='user_789',
        access_token='tok_test_abc',
        activo=True,
    )
    db.session.add(cred)
    db.session.flush()
    return cred


def _generar_firma_hmac(body_bytes, secret):
    """Genera firma HMAC-SHA256 como la envía Tienda Nube."""
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    return hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()


# -------------------------------------------------------------------
# Webhook — verificación HMAC
# -------------------------------------------------------------------


def test_webhook_sin_firma_retorna_401(app, client):
    """Webhook sin header HMAC devuelve 401."""
    _crear_empresa()
    db.session.commit()

    payload = json.dumps({'store_id': '12345', 'event': 'order/created', 'id': 1})

    response = client.post(
        '/tiendanube/webhook',
        data=payload,
        content_type='application/json',
    )

    assert response.status_code == 401
    data = response.get_json()
    assert 'Firma HMAC requerida' in data['error']


def test_webhook_firma_invalida_retorna_401(app, client):
    """Webhook con HMAC inválido devuelve 401."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id, tienda_id='12345', app_secret='mi_secreto')
    db.session.commit()

    payload_dict = {'store_id': '12345', 'event': 'order/created', 'id': 100}
    payload_bytes = json.dumps(payload_dict).encode('utf-8')

    response = client.post(
        '/tiendanube/webhook',
        data=payload_bytes,
        content_type='application/json',
        headers={'X-Linkedstore-HMAC-SHA256': 'firma_invalida_12345'},
    )

    assert response.status_code == 401
    data = response.get_json()
    assert 'Firma HMAC inválida' in data['error']


def test_webhook_store_inexistente_retorna_404(app, client):
    """Webhook con store_id desconocido devuelve 404."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id, tienda_id='99999', app_secret='secreto')
    db.session.commit()

    payload_dict = {'store_id': '00000', 'event': 'order/created', 'id': 100}
    payload_bytes = json.dumps(payload_dict).encode('utf-8')
    firma = _generar_firma_hmac(payload_bytes, 'secreto')

    response = client.post(
        '/tiendanube/webhook',
        data=payload_bytes,
        content_type='application/json',
        headers={'X-Linkedstore-HMAC-SHA256': firma},
    )

    assert response.status_code == 404
    data = response.get_json()
    assert 'Tienda no encontrada' in data['error']


def test_webhook_orden_creada_retorna_200(app, client):
    """Webhook order/created válido con HMAC correcto retorna 200."""
    empresa = _crear_empresa()
    app_secret = 'mi_secreto_hmac'
    _crear_credencial(empresa.id, tienda_id='55555', app_secret=app_secret)
    db.session.commit()

    payload_dict = {'store_id': '55555', 'event': 'order/created', 'id': 12345}
    payload_bytes = json.dumps(payload_dict).encode('utf-8')
    firma = _generar_firma_hmac(payload_bytes, app_secret)

    # Patch encolar_importar_orden para no depender de Redis/tasks
    from unittest.mock import patch

    with patch('app.routes.tiendanube.encolar_importar_orden') as mock_encolar:
        response = client.post(
            '/tiendanube/webhook',
            data=payload_bytes,
            content_type='application/json',
            headers={'X-Linkedstore-HMAC-SHA256': firma},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'

    # Verificar que se encoló la importación
    mock_encolar.assert_called_once_with(12345, empresa.id)

    # Verificar que se creó un SyncLog
    log = SyncLog.query.filter_by(
        empresa_id=empresa.id,
        recurso='webhook',
        direccion='importacion',
    ).first()
    assert log is not None
    assert 'order/created' in log.mensaje


def test_webhook_body_invalido_retorna_400(app, client):
    """Webhook con body no-JSON devuelve 400."""
    response = client.post(
        '/tiendanube/webhook',
        data='esto no es json',
        content_type='application/json',
        headers={'X-Linkedstore-HMAC-SHA256': 'cualquier_firma'},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert 'JSON inválido' in data['error']


def test_webhook_sin_store_id_retorna_400(app, client):
    """Webhook sin store_id en el payload devuelve 400."""
    payload_dict = {'event': 'order/created', 'id': 100}
    payload_bytes = json.dumps(payload_dict).encode('utf-8')

    response = client.post(
        '/tiendanube/webhook',
        data=payload_bytes,
        content_type='application/json',
        headers={'X-Linkedstore-HMAC-SHA256': 'cualquier_firma'},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert 'store_id requerido' in data['error']


def test_webhook_evento_no_soportado_retorna_200(app, client):
    """Webhook con evento no soportado retorna 200 pero no encola nada."""
    empresa = _crear_empresa()
    app_secret = 'secreto_evento'
    _crear_credencial(empresa.id, tienda_id='66666', app_secret=app_secret)
    db.session.commit()

    payload_dict = {'store_id': '66666', 'event': 'product/updated', 'id': 999}
    payload_bytes = json.dumps(payload_dict).encode('utf-8')
    firma = _generar_firma_hmac(payload_bytes, app_secret)

    from unittest.mock import patch

    with patch('app.routes.tiendanube.encolar_importar_orden') as mock_encolar:
        response = client.post(
            '/tiendanube/webhook',
            data=payload_bytes,
            content_type='application/json',
            headers={'X-Linkedstore-HMAC-SHA256': firma},
        )

    assert response.status_code == 200
    mock_encolar.assert_not_called()
