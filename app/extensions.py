"""
Inicialización de extensiones Flask.
Las extensiones se inicializan sin la app para permitir el patrón Application Factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect

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
