"""
Fixtures para tests de integración con ARCA homologación.

Estos tests requieren:
- Certificado y clave privada de homologación
- CUIT de testing
- Variables de entorno: ARCA_TEST_CUIT, ARCA_TEST_CERT_PATH, ARCA_TEST_KEY_PATH

Para ejecutar: pytest -m integracion_arca --arca-test -v
"""

import os

import pytest

from app.services.arca_client import ArcaClient
from app.services.wsfe_service import WSFEService


def pytest_addoption(parser):
    """Agrega opción --arca-test para habilitar tests de integración."""
    parser.addoption(
        '--arca-test',
        action='store_true',
        default=False,
        help='Ejecutar tests de integración con ARCA homologación',
    )


def pytest_collection_modifyitems(config, items):
    """Skipea tests marcados con integracion_arca si no se pasa --arca-test."""
    if not config.getoption('--arca-test'):
        skip_arca = pytest.mark.skip(
            reason='Requiere --arca-test para ejecutar tests de integración ARCA',
        )
        for item in items:
            if 'integracion_arca' in item.keywords:
                item.add_marker(skip_arca)


@pytest.fixture(scope='session')
def arca_test_config():
    """Config de ARCA homologación desde variables de entorno.

    Variables requeridas:
    - ARCA_TEST_CUIT: CUIT de testing (ej: 20304050607)
    - ARCA_TEST_CERT_PATH: Ruta absoluta al certificado .crt
    - ARCA_TEST_KEY_PATH: Ruta absoluta a la clave privada .key

    Variables opcionales:
    - ARCA_TEST_PUNTO_VENTA: Punto de venta (default: 1)
    """
    cuit = os.environ.get('ARCA_TEST_CUIT')
    cert_path = os.environ.get('ARCA_TEST_CERT_PATH')
    key_path = os.environ.get('ARCA_TEST_KEY_PATH')
    punto_venta = int(os.environ.get('ARCA_TEST_PUNTO_VENTA', '1'))

    errores = []
    if not cuit:
        errores.append('ARCA_TEST_CUIT no definida')
    if not cert_path:
        errores.append('ARCA_TEST_CERT_PATH no definida')
    elif not os.path.isfile(cert_path):
        errores.append(f'Certificado no encontrado: {cert_path}')
    if not key_path:
        errores.append('ARCA_TEST_KEY_PATH no definida')
    elif not os.path.isfile(key_path):
        errores.append(f'Clave privada no encontrada: {key_path}')

    if errores:
        pytest.skip(
            'Variables de entorno para ARCA homologación incompletas: ' + '; '.join(errores),
        )

    with open(cert_path, 'rb') as f:
        certificado = f.read()
    with open(key_path, 'rb') as f:
        clave_privada = f.read()

    return {
        'cuit': cuit,
        'certificado': certificado,
        'clave_privada': clave_privada,
        'ambiente': 'testing',
        'punto_venta': punto_venta,
    }


@pytest.fixture(scope='session')
def arca_client(arca_test_config):
    """ArcaClient real conectado a homologación.

    Scope de sesión para reutilizar autenticación WSAA entre tests.
    """
    client = ArcaClient(
        cuit=arca_test_config['cuit'],
        certificado=arca_test_config['certificado'],
        clave_privada=arca_test_config['clave_privada'],
        ambiente='testing',
    )
    yield client
    client.close()


@pytest.fixture(scope='session')
def wsfe_service(arca_client):
    """WSFEService real conectado a homologación."""
    return WSFEService(arca_client)


@pytest.fixture(scope='session')
def punto_venta(arca_test_config):
    """Punto de venta de testing."""
    return arca_test_config['punto_venta']


@pytest.fixture(scope='session')
def cuit_testing(arca_test_config):
    """CUIT de testing (solo dígitos)."""
    import re

    return re.sub(r'\D+', '', arca_test_config['cuit'])
