"""
Inicialización de extensiones Flask.
Las extensiones se inicializan sin la app para permitir el patrón Application Factory.
"""

import logging

from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

logger = logging.getLogger(__name__)

# Base de datos
db = SQLAlchemy()

# Migraciones
migrate = Migrate()

# Autenticación
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'

# Hash de contraseñas
bcrypt = Bcrypt()

# Protección CSRF
csrf = CSRFProtect()

# Redis / RQ
redis_client = None
rq_queues = {}


def init_redis_rq(app):
    """Inicializa Redis y las colas RQ sin romper la aplicación si Redis no responde."""
    global redis_client, rq_queues

    redis_client = None
    rq_queues = {}

    redis_url = app.config.get('REDIS_URL')
    nombres_colas = app.config.get('RQ_QUEUES', [])
    redis_disponible = False

    if not redis_url:
        app.extensions['redis'] = {
            'client': None,
            'queues': {},
            'available': False,
        }
        return

    try:
        redis_client = Redis.from_url(redis_url)
        redis_client.ping()
        rq_queues = {nombre: Queue(nombre, connection=redis_client) for nombre in nombres_colas}
        redis_disponible = True
    except RedisError as exc:
        logger.warning('Redis no disponible en %s: %s', redis_url, exc)

    app.extensions['redis'] = {
        'client': redis_client,
        'queues': rq_queues,
        'available': redis_disponible,
    }
