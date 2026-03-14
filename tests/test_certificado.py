"""Tests de utilidades de certificado X.509 y propiedades del modelo Facturador."""

import os
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app import create_app
from app.extensions import db as _db
from app.models import Empresa
from app.models.facturador import Facturador
from app.utils.certificado import extraer_info_certificado

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')


# =====================================================================
# Helpers para generar certificados de prueba
# =====================================================================


def _generar_clave_privada():
    """Genera una clave RSA de 2048 bits para tests."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _generar_certificado(
    dias_validez=365, cn_sujeto='Test CUIT 20123456783', cn_emisor='AC Testing ARCA', formato='pem'
):
    """Genera un certificado X.509 auto-firmado para tests.

    Args:
        dias_validez: días desde hoy hasta el vencimiento.
                      Negativo para certificados ya vencidos.
        cn_sujeto: Common Name del sujeto.
        cn_emisor: Common Name del emisor.
        formato: 'pem' o 'der'.

    Returns:
        bytes del certificado en el formato indicado.
    """
    clave = _generar_clave_privada()

    sujeto = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, cn_sujeto),
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'AR'),
        ]
    )
    emisor = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, cn_emisor),
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'AR'),
        ]
    )

    ahora = datetime.now(timezone.utc)
    if dias_validez >= 0:
        valido_desde = ahora - timedelta(days=1)
        valido_hasta = ahora + timedelta(days=dias_validez)
    else:
        # Certificado ya vencido
        valido_desde = ahora + timedelta(days=dias_validez) - timedelta(days=30)
        valido_hasta = ahora + timedelta(days=dias_validez)

    cert = (
        x509.CertificateBuilder()
        .subject_name(sujeto)
        .issuer_name(emisor)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valido_desde)
        .not_valid_after(valido_hasta)
        .sign(clave, hashes.SHA256())
    )

    if formato == 'der':
        return cert.public_bytes(serialization.Encoding.DER)
    return cert.public_bytes(serialization.Encoding.PEM)


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def app():
    """App de testing."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=True,
    )

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def empresa(app):
    """Crea una empresa de prueba."""
    emp = Empresa(nombre='Ferretería Cert Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp


def _crear_facturador(empresa_id, **kwargs):
    """Helper para crear un facturador de prueba."""
    defaults = {
        'nombre': 'Facturador Test',
        'razon_social': 'Test SA',
        'cuit': '20-12345678-3',
        'condicion_iva_id': 1,
        'punto_venta': 1,
        'ambiente': 'testing',
        'activo': True,
        'empresa_id': empresa_id,
    }
    defaults.update(kwargs)
    facturador = Facturador(**defaults)
    _db.session.add(facturador)
    _db.session.commit()
    return facturador


# =====================================================================
# Tests de extraer_info_certificado
# =====================================================================


class TestExtraerInfoCertificado:
    """Tests de la función extraer_info_certificado."""

    def test_extraer_info_certificado_pem(self):
        """Parsea un certificado PEM y extrae la info correcta."""
        cert_pem = _generar_certificado(
            dias_validez=90,
            cn_sujeto='CUIT 20304050607',
            cn_emisor='AC ARCA Testing',
            formato='pem',
        )

        info = extraer_info_certificado(cert_pem)

        assert 'vencimiento' in info
        assert 'emisor' in info
        assert 'sujeto' in info
        assert 'numero_serie' in info
        assert 'valido_desde' in info

        assert isinstance(info['vencimiento'], datetime)
        assert isinstance(info['valido_desde'], datetime)
        assert info['sujeto'] == 'CUIT 20304050607'
        assert info['emisor'] == 'AC ARCA Testing'
        assert info['vencimiento'] > datetime.now(timezone.utc).replace(tzinfo=None)

    def test_extraer_info_certificado_der(self):
        """Parsea un certificado DER y extrae la info correcta."""
        cert_der = _generar_certificado(
            dias_validez=60,
            cn_sujeto='CUIT 27111222333',
            cn_emisor='AC ARCA Prod',
            formato='der',
        )

        info = extraer_info_certificado(cert_der)

        assert info['sujeto'] == 'CUIT 27111222333'
        assert info['emisor'] == 'AC ARCA Prod'
        assert isinstance(info['vencimiento'], datetime)

    def test_extraer_info_certificado_invalido(self):
        """Datos inválidos levantan ValueError."""
        with pytest.raises(ValueError, match='No se pudo parsear'):
            extraer_info_certificado(b'esto no es un certificado')

    def test_extraer_info_certificado_vacio(self):
        """Datos vacíos levantan ValueError."""
        with pytest.raises(ValueError, match='No se proporcionaron datos'):
            extraer_info_certificado(b'')

    def test_extraer_info_certificado_none(self):
        """None como entrada levanta ValueError."""
        with pytest.raises(ValueError, match='No se proporcionaron datos'):
            extraer_info_certificado(None)

    def test_numero_serie_hexadecimal(self):
        """El número de serie se retorna en formato hexadecimal."""
        cert_pem = _generar_certificado(dias_validez=30)

        info = extraer_info_certificado(cert_pem)

        # Debe ser un string hexadecimal válido
        assert isinstance(info['numero_serie'], str)
        int(info['numero_serie'], 16)  # No levanta ValueError


# =====================================================================
# Tests de propiedades de certificado en el modelo Facturador
# =====================================================================


class TestFacturadorCertificado:
    """Tests de las propiedades de estado de certificado del modelo."""

    def test_dias_para_vencimiento_futuro(self, app, empresa):
        """Certificado que vence en 60 días retorna ~60."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=60)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
        )

        dias = facturador.dias_para_vencimiento
        assert dias is not None
        # Tolerancia de 1 día por posible diferencia de horas
        assert 59 <= dias <= 61

    def test_dias_para_vencimiento_pasado(self, app, empresa):
        """Certificado ya vencido retorna valor negativo."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-99999999-1',
        )

        dias = facturador.dias_para_vencimiento
        assert dias is not None
        assert dias < 0

    def test_dias_para_vencimiento_sin_fecha(self, app, empresa):
        """Sin fecha de vencimiento retorna None."""
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=None,
            cuit='20-88888888-1',
        )

        assert facturador.dias_para_vencimiento is None

    def test_certificado_vencido(self, app, empresa):
        """certificado_vencido es True cuando ya expiró."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-77777777-1',
        )

        assert facturador.certificado_vencido is True

    def test_certificado_no_vencido(self, app, empresa):
        """certificado_vencido es False cuando aún no expiró."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=90)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-66666666-1',
        )

        assert facturador.certificado_vencido is False

    def test_certificado_por_vencer(self, app, empresa):
        """certificado_por_vencer es True dentro de los 30 días."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=15)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-55555555-1',
        )

        assert facturador.certificado_por_vencer is True

    def test_certificado_no_por_vencer(self, app, empresa):
        """certificado_por_vencer es False con más de 30 días."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=90)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-44444444-1',
        )

        assert facturador.certificado_por_vencer is False

    def test_estado_certificado_vigente(self, app, empresa):
        """estado_certificado retorna 'vigente' con más de 30 días."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=90)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-33333333-1',
        )

        assert facturador.estado_certificado == 'vigente'

    def test_estado_certificado_por_vencer(self, app, empresa):
        """estado_certificado retorna 'por_vencer' dentro de 30 días."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=10)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-22222222-1',
        )

        assert facturador.estado_certificado == 'por_vencer'

    def test_estado_certificado_vencido(self, app, empresa):
        """estado_certificado retorna 'vencido' cuando ya expiró."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            cuit='20-11111111-1',
        )

        assert facturador.estado_certificado == 'vencido'

    def test_estado_certificado_sin_certificado(self, app, empresa):
        """estado_certificado retorna 'sin_certificado' sin fecha."""
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=None,
            cuit='20-10101010-1',
        )

        assert facturador.estado_certificado == 'sin_certificado'

    def test_to_dict_incluye_estado_certificado(self, app, empresa):
        """to_dict incluye los nuevos campos de certificado."""
        vencimiento = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=90)
        facturador = _crear_facturador(
            empresa.id,
            certificado_vencimiento=vencimiento,
            certificado_emisor='AC ARCA',
            certificado_sujeto='CUIT 20123456783',
            cuit='20-09090909-1',
        )

        datos = facturador.to_dict()
        assert 'estado_certificado' in datos
        assert datos['estado_certificado'] == 'vigente'
        assert datos['certificado_emisor'] == 'AC ARCA'
        assert datos['certificado_sujeto'] == 'CUIT 20123456783'
