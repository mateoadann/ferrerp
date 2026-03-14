"""
FerrERP - Sistema de gestión para ferreterías
Application Factory Pattern
"""

import os

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import config
from .extensions import bcrypt, csrf, db, init_redis_rq, login_manager, migrate


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
    init_redis_rq(app)

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
        tiendanube_bp,
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
    app.register_blueprint(tiendanube_bp)


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

        return {
            'app_name': app.config.get('APP_NAME', 'FerrERP'),
            'current_year': ahora_argentina().year,
            'get_config': get_config,
            'precios_con_iva': get_config('precios_con_iva', True),
            'empresa_actual': empresa_actual,
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
