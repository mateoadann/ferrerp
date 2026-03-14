"""
FerrERP - Sistema de gestión para ferreterías
Application Factory Pattern
"""

import os

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import config
from .extensions import bcrypt, csrf, db, login_manager, migrate


def create_app(config_name=None):
    """
    Application Factory - Crea y configura la aplicación Flask.

    Args:
        config_name: Nombre de la configuración ('development', 'testing', 'production')

    Returns:
        Flask app configurada
    """
    # Cargar variables de entorno
    load_dotenv()

    # Crear aplicación
    app = Flask(__name__)

    # Determinar configuración
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    # Aplicar configuración
    app.config.from_object(config[config_name])

    # Inicializar extensiones
    init_extensions(app)

    # Registrar blueprints
    register_blueprints(app)

    # Registrar comandos CLI
    register_commands(app)

    # Configurar contexto de templates
    register_template_context(app)

    # Registrar manejadores de errores
    register_error_handlers(app)

    # ProxyFix para funcionar detrás de nginx (X-Forwarded-Proto, X-Forwarded-Host)
    if config_name == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    return app


def init_extensions(app):
    """Inicializa las extensiones con la aplicación."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # Configurar user_loader para Flask-Login
    from .models.usuario import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))


def register_blueprints(app):
    """Registra todos los blueprints de la aplicación."""
    from .routes import (
        auth_bp,
        caja_bp,
        clientes_bp,
        compras_bp,
        configuracion_bp,
        dashboard_bp,
        facturacion_bp,
        inventario_bp,
        presupuestos_bp,
        productos_bp,
        proveedores_bp,
        reportes_bp,
        superadmin_bp,
        ventas_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(presupuestos_bp)
    app.register_blueprint(caja_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(configuracion_bp)
    app.register_blueprint(facturacion_bp)
    app.register_blueprint(superadmin_bp)


def register_commands(app):
    """Registra comandos CLI personalizados."""
    import click

    @app.cli.command('init-db')
    def init_db():
        """Inicializa la base de datos."""
        db.create_all()
        print('Base de datos inicializada.')

    @app.cli.command('seed')
    def seed():
        """Carga datos iniciales de prueba."""
        from seeds.seed_data import run_seeds

        run_seeds()
        print('Datos de prueba cargados.')

    @app.cli.command('crear-superadmin')
    @click.option('--email', required=True, help='Email del superadmin')
    @click.option('--nombre', required=True, help='Nombre del superadmin')
    @click.option('--password', required=True, help='Contraseña del superadmin')
    def crear_superadmin(email, nombre, password):
        """Crea el usuario superadmin (único en el sistema)."""
        from .models import Usuario

        existente = Usuario.query.filter_by(rol='superadmin').first()
        if existente:
            print(f'Ya existe un superadmin registrado: {existente.email}')
            return

        usuario = Usuario(
            email=email.lower(),
            nombre=nombre,
            rol='superadmin',
            activo=True,
            empresa_id=None,
        )
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        print(f'Superadmin creado exitosamente: {email}')

    @app.cli.command('actualizar-info-certs')
    def actualizar_info_certs():
        """Actualiza la info de certificados de facturadores existentes.

        Lee cada certificado almacenado, extrae vencimiento, emisor y sujeto,
        y actualiza los campos correspondientes. Útil para backfill después
        de agregar los campos de info de certificado.
        """
        from .models.facturador import Facturador
        from .utils.certificado import extraer_info_certificado
        from .utils.crypto import desencriptar

        facturadores = Facturador.query.filter(
            Facturador.certificado.isnot(None),
            Facturador.certificado_vencimiento.is_(None),
        ).all()

        if not facturadores:
            print('No hay facturadores con certificados pendientes de procesar.')
            return

        print(f'Procesando {len(facturadores)} facturador(es)...')
        actualizados = 0
        errores = 0

        for f in facturadores:
            try:
                cert_bytes = desencriptar(f.certificado)
                info = extraer_info_certificado(cert_bytes)
                f.certificado_vencimiento = info['vencimiento']
                f.certificado_emisor = info['emisor']
                f.certificado_sujeto = info['sujeto']
                actualizados += 1
                print(f'  OK: {f.nombre} ({f.cuit}) — vence {info["vencimiento"]}')
            except Exception as exc:
                errores += 1
                print(f'  ERROR: {f.nombre} ({f.cuit}) — {exc}')

        db.session.commit()
        print(f'\nResultado: {actualizados} actualizados, {errores} con error.')

    @app.cli.command('encrypt-certs')
    @click.option(
        '--dry-run',
        is_flag=True,
        help='Solo muestra qué se encriptaría sin modificar.',
    )
    def encrypt_certs(dry_run):
        """Encripta certificados y claves privadas existentes sin encriptar.

        Busca registros en Facturador y Empresa que tengan certificados/claves
        sin el prefijo de encriptación y los encripta in-place.
        Requiere ENCRYPTION_KEY configurada.
        """
        from .models import Empresa
        from .models.facturador import Facturador
        from .utils.crypto import PREFIJO_ENCRIPTADO, encriptar, obtener_fernet

        if obtener_fernet() is None:
            print('ERROR: ENCRYPTION_KEY no está configurada.')
            print(
                'Generar con: python -c '
                '"from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
            return

        total_encriptados = 0
        total_ya_encriptados = 0

        # Procesar Facturadores
        facturadores = Facturador.query.all()
        print(f'Revisando {len(facturadores)} facturador(es)...')

        for fac in facturadores:
            for campo in ('certificado', 'clave_privada'):
                datos = getattr(fac, campo)
                if not datos:
                    continue
                if datos.startswith(PREFIJO_ENCRIPTADO):
                    total_ya_encriptados += 1
                    continue
                if dry_run:
                    print(
                        f'  [DRY-RUN] Facturador #{fac.id} '
                        f'"{fac.nombre}": {campo} se encriptaría'
                    )
                else:
                    setattr(fac, campo, encriptar(datos))
                    print(f'  Facturador #{fac.id} ' f'"{fac.nombre}": {campo} encriptado')
                total_encriptados += 1

        # Procesar Empresas (campos deprecados)
        empresas = Empresa.query.all()
        print(f'Revisando {len(empresas)} empresa(s) (campos legacy)...')

        for emp in empresas:
            for campo in ('certificado_arca', 'clave_privada_arca'):
                datos = getattr(emp, campo, None)
                if not datos:
                    continue
                if datos.startswith(PREFIJO_ENCRIPTADO):
                    total_ya_encriptados += 1
                    continue
                if dry_run:
                    print(
                        f'  [DRY-RUN] Empresa #{emp.id} ' f'"{emp.nombre}": {campo} se encriptaría'
                    )
                else:
                    setattr(emp, campo, encriptar(datos))
                    print(f'  Empresa #{emp.id} ' f'"{emp.nombre}": {campo} encriptado')
                total_encriptados += 1

        if not dry_run and total_encriptados > 0:
            db.session.commit()

        print('\nResumen:')
        print(f'  Encriptados: {total_encriptados}')
        print(f'  Ya encriptados: {total_ya_encriptados}')
        if dry_run and total_encriptados > 0:
            print('  (modo dry-run, no se modificó nada)')


def register_template_context(app):
    """Registra variables y funciones globales para templates."""

    @app.context_processor
    def inject_globals():
        from flask_login import current_user

        from .models.configuracion import Configuracion
        from .utils.helpers import ahora_argentina

        # Obtener configuración del negocio (filtrada por empresa)
        def get_config(clave, default=None):
            if not current_user.is_authenticated:
                return default
            if current_user.empresa_id is None:
                return default
            config_item = Configuracion.query.filter_by(
                clave=clave, empresa_id=current_user.empresa_id
            ).first()
            return config_item.get_valor() if config_item else default

        empresa_actual = None
        if current_user.is_authenticated and current_user.empresa:
            empresa_actual = current_user.empresa

        # Alertas de certificados por vencer/vencidos
        alertas_certs = []
        if (
            current_user.is_authenticated
            and current_user.empresa_id is not None
            and getattr(current_user, 'es_administrador', False)
        ):
            from .models.facturador import Facturador

            facturadores_activos = Facturador.query.filter_by(
                empresa_id=current_user.empresa_id,
                activo=True,
            ).all()
            for f in facturadores_activos:
                if f.estado_certificado in ('vencido', 'por_vencer'):
                    alertas_certs.append(f)

        return {
            'app_name': app.config.get('APP_NAME', 'FerrERP'),
            'current_year': ahora_argentina().year,
            'get_config': get_config,
            'precios_con_iva': get_config('precios_con_iva', True),
            'empresa_actual': empresa_actual,
            'alertas_certificados': alertas_certs,
        }

    # Filtros personalizados para Jinja2
    @app.template_filter('combine')
    def combine_filter(d, other):
        """Combina dos diccionarios (equivalente a {**d, **other})."""
        result = dict(d)
        result.update(other)
        return result

    @app.template_filter('stock')
    def stock_filter(value, unidad_medida='unidad'):
        """Formatea una cantidad de stock según la unidad de medida."""
        if value is None:
            return '0'
        if unidad_medida in ('unidad', 'par'):
            return f'{int(value)}'
        return f'{float(value):.2f}'

    @app.template_filter('currency')
    def currency_filter(value):
        """Formatea un número como moneda."""
        if value is None:
            return '$0.00'
        return f'${value:,.2f}'

    @app.template_filter('datetime')
    def datetime_filter(value, format='%d/%m/%Y %H:%M'):
        """Formatea una fecha/hora."""
        if value is None:
            return ''
        return value.strftime(format)

    @app.template_filter('date')
    def date_filter(value, format='%d/%m/%Y'):
        """Formatea una fecha."""
        if value is None:
            return ''
        return value.strftime(format)


def register_error_handlers(app):
    """Registra manejadores de errores personalizados."""
    from flask import render_template

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
