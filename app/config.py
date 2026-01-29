import os
from datetime import timedelta


class Config:
    """Configuración base."""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-cambiar-en-produccion')

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_PROTECTION = 'strong'

    # Aplicación
    APP_NAME = os.environ.get('APP_NAME', 'FerrERP')
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 20))

    # WTForms
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora


class DevelopmentConfig(Config):
    """Configuración de desarrollo."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///ferrerp_dev.db'  # SQLite por defecto para desarrollo facil
    )
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'false').lower() == 'true'


class TestingConfig(Config):
    """Configuración de pruebas."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'TEST_DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/ferrerp_test'
    )
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = False


class ProductionConfig(Config):
    """Configuración de producción."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    # Seguridad adicional en producción
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
