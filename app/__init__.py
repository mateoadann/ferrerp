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

    # ------------------------------------------------------------------
    # Comandos CLI de Tienda Nube
    # ------------------------------------------------------------------

    @app.cli.command('tn-status')
    @click.option('--empresa-id', type=int, default=None, help='ID de la empresa (opcional)')
    def tn_status(empresa_id):
        """Muestra el estado de la integración Tienda Nube."""
        from .models.empresa import Empresa
        from .models.tiendanube import ProductoTiendaNube, SyncLog, TiendaNubeCredencial

        if empresa_id:
            cred = TiendaNubeCredencial.query.filter_by(empresa_id=empresa_id).first()
            if not cred:
                click.echo(
                    click.style(
                        f'La empresa {empresa_id} no tiene credenciales de Tienda Nube.',
                        fg='red',
                    )
                )
                return
            credenciales = [cred]
        else:
            credenciales = TiendaNubeCredencial.query.all()
            if not credenciales:
                click.echo(
                    click.style('No hay empresas con credenciales de Tienda Nube.', fg='yellow')
                )
                return

        for cred in credenciales:
            empresa = db.session.get(Empresa, cred.empresa_id)
            nombre = empresa.nombre if empresa else '(desconocida)'

            click.echo('')
            click.echo(
                click.style(
                    f'=== Empresa: {nombre} (ID: {cred.empresa_id}) ===', fg='cyan', bold=True
                )
            )

            # Estado de la conexión
            estado = (
                click.style('ACTIVA', fg='green')
                if cred.activo
                else click.style('INACTIVA', fg='red')
            )
            click.echo(f'  Conexión:      {estado}')
            click.echo(f'  Tienda ID:     {cred.tienda_id_externo or "(sin configurar)"}')
            tiene_token = 'Sí' if cred.access_token else 'No'
            click.echo(f'  Access Token:  {tiene_token}')

            # Productos vinculados
            total_productos = ProductoTiendaNube.query.filter_by(
                empresa_id=cred.empresa_id,
            ).count()
            activos = ProductoTiendaNube.query.filter_by(
                empresa_id=cred.empresa_id,
                activo=True,
            ).count()
            con_error = ProductoTiendaNube.query.filter_by(
                empresa_id=cred.empresa_id,
                estado_sync='error',
            ).count()
            click.echo(
                f'  Productos:     {total_productos} total, {activos} activos, {con_error} con error'
            )

            # Último sync
            ultimo_log = (
                SyncLog.query.filter_by(
                    empresa_id=cred.empresa_id,
                )
                .order_by(SyncLog.created_at.desc())
                .first()
            )
            if ultimo_log:
                click.echo(
                    f'  Último sync:   {ultimo_log.created_at} [{ultimo_log.estado}] {ultimo_log.recurso}'
                )
            else:
                click.echo('  Último sync:   (sin registros)')

        # Estado de Redis
        click.echo('')
        redis_info = app.extensions.get('redis', {})
        if redis_info.get('available'):
            click.echo(click.style('  Redis: conectado', fg='green'))
        else:
            click.echo(click.style('  Redis: no disponible', fg='yellow'))

        click.echo('')

    @app.cli.command('tn-sync')
    @click.option('--empresa-id', type=int, required=True, help='ID de la empresa')
    def tn_sync(empresa_id):
        """Ejecuta sincronización masiva de stock con Tienda Nube."""
        from .models.empresa import Empresa
        from .models.tiendanube import TiendaNubeCredencial
        from .services.tiendanube_service import sincronizar_stock_masivo

        # Validar empresa
        empresa = db.session.get(Empresa, empresa_id)
        if not empresa:
            click.echo(click.style(f'No existe la empresa con ID {empresa_id}.', fg='red'))
            return

        # Validar credenciales activas
        cred = TiendaNubeCredencial.query.filter_by(
            empresa_id=empresa_id,
            activo=True,
        ).first()
        if not cred:
            click.echo(
                click.style(
                    f'La empresa "{empresa.nombre}" no tiene credenciales activas de Tienda Nube.',
                    fg='red',
                )
            )
            return

        click.echo(f'Iniciando sincronización de stock para "{empresa.nombre}"...')

        try:
            resultado = sincronizar_stock_masivo(empresa_id)
        except Exception as e:
            click.echo(click.style(f'Error durante la sincronización: {e}', fg='red'))
            return

        # Mostrar resultados
        click.echo('')
        click.echo(click.style('Resultado de sincronización:', bold=True))
        click.echo(f'  Total:    {resultado["total"]}')
        click.echo(click.style(f'  Exitosos: {resultado["exitosos"]}', fg='green'))

        if resultado['errores'] > 0:
            click.echo(click.style(f'  Errores:  {resultado["errores"]}', fg='red'))
            for detalle in resultado.get('detalle_errores', []):
                click.echo(
                    click.style(
                        f'    - Producto {detalle["producto_id"]} '
                        f'(TN: {detalle["tn_producto_id"]}): {detalle["error"]}',
                        fg='red',
                    )
                )
        else:
            click.echo(click.style('  Errores:  0', fg='green'))

        click.echo('')

    @app.cli.command('tn-webhooks')
    @click.option('--empresa-id', type=int, required=True, help='ID de la empresa')
    @click.option(
        '--action',
        type=click.Choice(['registrar', 'eliminar', 'listar'], case_sensitive=False),
        required=True,
        help='Acción a ejecutar',
    )
    @click.option(
        '--webhook-url', default=None, help='URL pública del endpoint webhook (para registrar)'
    )
    def tn_webhooks(empresa_id, action, webhook_url):
        """Gestiona webhooks de Tienda Nube."""
        from .models.empresa import Empresa
        from .models.tiendanube import TiendaNubeCredencial
        from .services.tiendanube_service import (
            eliminar_webhooks_tn,
            obtener_cliente_tn,
            registrar_webhooks_tn,
        )

        # Validar empresa
        empresa = db.session.get(Empresa, empresa_id)
        if not empresa:
            click.echo(click.style(f'No existe la empresa con ID {empresa_id}.', fg='red'))
            return

        # Validar credenciales activas
        cred = TiendaNubeCredencial.query.filter_by(
            empresa_id=empresa_id,
            activo=True,
        ).first()
        if not cred:
            click.echo(
                click.style(
                    f'La empresa "{empresa.nombre}" no tiene credenciales activas de Tienda Nube.',
                    fg='red',
                )
            )
            return

        try:
            if action == 'registrar':
                if not webhook_url:
                    click.echo(
                        click.style(
                            'Se requiere --webhook-url para registrar webhooks.',
                            fg='red',
                        )
                    )
                    return

                click.echo(f'Registrando webhooks para "{empresa.nombre}"...')
                creados = registrar_webhooks_tn(empresa_id, webhook_url=webhook_url)
                click.echo(click.style(f'Webhooks registrados: {len(creados)}', fg='green'))
                for wh in creados:
                    click.echo(f'  - ID: {wh.get("id")}  Evento: {wh.get("event")}')

            elif action == 'eliminar':
                click.echo(f'Eliminando webhooks para "{empresa.nombre}"...')
                eliminar_webhooks_tn(empresa_id)
                click.echo(click.style('Webhooks eliminados correctamente.', fg='green'))

            elif action == 'listar':
                click.echo(f'Webhooks registrados para "{empresa.nombre}":')
                client = obtener_cliente_tn(empresa_id)
                webhooks = client.listar_webhooks()
                if not webhooks:
                    click.echo(click.style('  (sin webhooks registrados)', fg='yellow'))
                else:
                    for wh in webhooks:
                        click.echo(
                            f'  ID: {wh.get("id"):>6}  '
                            f'Evento: {wh.get("event", "?"):<30}  '
                            f'URL: {wh.get("url", "?")}'
                        )

        except Exception as e:
            click.echo(click.style(f'Error: {e}', fg='red'))

        click.echo('')

    @app.cli.command('tn-logs')
    @click.option('--empresa-id', type=int, default=None, help='ID de la empresa (opcional)')
    @click.option(
        '--limit', 'limite', type=int, default=20, help='Cantidad de registros (default: 20)'
    )
    def tn_logs(empresa_id, limite):
        """Muestra los últimos registros de sincronización de Tienda Nube."""
        from .models.tiendanube import SyncLog

        query = SyncLog.query.order_by(SyncLog.created_at.desc())

        if empresa_id:
            query = query.filter_by(empresa_id=empresa_id)

        logs = query.limit(limite).all()

        if not logs:
            click.echo(click.style('No hay registros de sincronización.', fg='yellow'))
            return

        click.echo('')
        click.echo(
            click.style(
                f'{"ID":>6}  {"Empresa":>7}  {"Recurso":<12}  {"Dirección":<13}  '
                f'{"Estado":<10}  {"Fecha":<20}  Mensaje',
                bold=True,
            )
        )
        click.echo('-' * 110)

        for log in logs:
            # Colorear el estado
            if log.estado == 'exitoso':
                estado = click.style(f'{log.estado:<10}', fg='green')
            elif log.estado == 'error':
                estado = click.style(f'{log.estado:<10}', fg='red')
            else:
                estado = click.style(f'{log.estado:<10}', fg='yellow')

            fecha = log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else ''
            mensaje = (log.mensaje or '')[:50]

            click.echo(
                f'{log.id:>6}  {log.empresa_id:>7}  {log.recurso:<12}  '
                f'{log.direccion:<13}  {estado}  {fecha:<20}  {mensaje}'
            )


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
