"""
FerrERP - Sistema de gestión para ferreterías
Application Factory Pattern
"""

import os
from flask import Flask
from dotenv import load_dotenv

from .config import config
from .extensions import db, migrate, login_manager, bcrypt, csrf


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
        return Usuario.query.get(int(user_id))


def register_blueprints(app):
    """Registra todos los blueprints de la aplicación."""
    from .routes import (
        auth_bp,
        dashboard_bp,
        productos_bp,
        inventario_bp,
        proveedores_bp,
        compras_bp,
        clientes_bp,
        ventas_bp,
        presupuestos_bp,
        caja_bp,
        reportes_bp,
        configuracion_bp
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


def register_commands(app):
    """Registra comandos CLI personalizados."""

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


def register_template_context(app):
    """Registra variables y funciones globales para templates."""

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        from .models.configuracion import Configuracion

        # Obtener configuración del negocio
        def get_config(clave, default=None):
            config_item = Configuracion.query.filter_by(clave=clave).first()
            return config_item.get_valor() if config_item else default

        return {
            'app_name': app.config.get('APP_NAME', 'FerrERP'),
            'current_year': datetime.now().year,
            'get_config': get_config,
            'iva_porcentaje': get_config('iva_porcentaje', 21),
            'precios_con_iva': get_config('precios_con_iva', True),
        }

    # Filtros personalizados para Jinja2
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
