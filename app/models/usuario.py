"""Modelo de Usuario."""

from datetime import datetime
from flask_login import UserMixin
from ..extensions import db, bcrypt


class Usuario(UserMixin, db.Model):
    """Modelo de usuario del sistema."""

    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    rol = db.Column(
        db.Enum('administrador', 'vendedor', name='rol_usuario'),
        nullable=False,
        default='vendedor'
    )
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    ventas = db.relationship('Venta', backref='usuario', lazy='dynamic')
    movimientos_stock = db.relationship('MovimientoStock', backref='usuario', lazy='dynamic')
    movimientos_caja = db.relationship('MovimientoCaja', backref='usuario', lazy='dynamic')

    def __repr__(self):
        return f'<Usuario {self.email}>'

    def set_password(self, password):
        """Establece el hash de la contraseña."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Verifica la contraseña."""
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def es_administrador(self):
        """Verifica si el usuario es administrador."""
        return self.rol == 'administrador'

    @property
    def es_admin(self):
        """Alias para es_administrador."""
        return self.es_administrador

    @property
    def nombre_completo(self):
        """Retorna el nombre completo del usuario."""
        return self.nombre

    @property
    def iniciales(self):
        """Obtiene las iniciales del nombre."""
        partes = self.nombre.split()
        if len(partes) >= 2:
            return f'{partes[0][0]}{partes[1][0]}'.upper()
        return self.nombre[0].upper() if self.nombre else 'U'

    def to_dict(self):
        """Convierte el usuario a diccionario."""
        return {
            'id': self.id,
            'email': self.email,
            'nombre': self.nombre,
            'rol': self.rol,
            'activo': self.activo,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
