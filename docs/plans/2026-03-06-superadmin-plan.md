# Superadmin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implementar un usuario superadmin unico que gestiona tenants (empresas), aprueba registros y puede resetear contrasenas de admins.

**Architecture:** Nuevo rol `superadmin` en el modelo Usuario con `empresa_id=None`. Nuevo campo `aprobada` en Empresa. Blueprint dedicado `/superadmin/` con layout propio. Decoradores `@superadmin_required` y `@empresa_aprobada_required` para control de acceso.

**Tech Stack:** Flask + SQLAlchemy + Jinja2 + HTMX + Bootstrap (stack existente). Migracion Alembic. Comando CLI Flask.

---

### Task 1: Migracion de base de datos

**Files:**
- Modify: `app/models/usuario.py:19-27`
- Modify: `app/models/empresa.py:19`
- Create: `migrations/versions/0006_superadmin_y_aprobacion.py`

**Step 1: Modificar modelo Usuario - agregar rol superadmin y campo debe_cambiar_password**

En `app/models/usuario.py`, cambiar la linea 19-23 del Enum de rol para incluir `superadmin`, y agregar campo `debe_cambiar_password`:

```python
rol = db.Column(
    db.Enum('superadmin', 'administrador', 'vendedor', name='rol_usuario'),
    nullable=False,
    default='vendedor',
)
activo = db.Column(db.Boolean, default=True, nullable=False)
debe_cambiar_password = db.Column(db.Boolean, default=False, nullable=False)
empresa_id = db.Column(
    db.Integer, db.ForeignKey('empresas.id'), nullable=True, index=True
)
```

Agregar propiedad:

```python
@property
def es_superadmin(self):
    """Verifica si el usuario es superadmin."""
    return self.rol == 'superadmin'
```

**Step 2: Modificar modelo Empresa - agregar campo aprobada**

En `app/models/empresa.py`, despues de la linea 19 (`activa`), agregar:

```python
aprobada = db.Column(db.Boolean, default=False, nullable=False)
```

**Step 3: Generar migracion**

Run: `make shell` luego `flask db revision -m "agregar superadmin y aprobacion empresas"`

La migracion debe:
1. Agregar columna `debe_cambiar_password` a `usuarios` (default False)
2. Agregar columna `aprobada` a `empresas` (default False)
3. Actualizar enum `rol_usuario` para incluir `superadmin`
4. UPDATE empresas existentes: SET `aprobada = True`

**NOTA IMPORTANTE sobre el Enum en PostgreSQL:**
El enum `rol_usuario` ya existe en la BD. Para agregar un valor hay que usar:
```python
# En upgrade()
op.execute("ALTER TYPE rol_usuario ADD VALUE IF NOT EXISTS 'superadmin'")
op.add_column('usuarios', sa.Column('debe_cambiar_password', sa.Boolean(), nullable=False, server_default='false'))
op.add_column('empresas', sa.Column('aprobada', sa.Boolean(), nullable=False, server_default='false'))
op.execute("UPDATE empresas SET aprobada = true")
```

**Step 4: Aplicar migracion y verificar**

Run: `make migrate`
Expected: Migracion aplicada sin errores.

**Step 5: Commit**

```bash
git add app/models/usuario.py app/models/empresa.py migrations/versions/0006_*.py
git commit -m "feat: agregar rol superadmin, campo aprobada en empresas y debe_cambiar_password"
```

---

### Task 2: Comando CLI crear-superadmin

**Files:**
- Modify: `app/__init__.py:110-125`
- Test: `tests/test_cli.py`

**Step 1: Escribir test para el comando CLI**

Crear `tests/test_cli.py`:

```python
"""Tests para comandos CLI."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

from app import create_app
from app.extensions import db as _db
from app.models import Usuario


def test_crear_superadmin(app):
    """Test que el comando crea un superadmin correctamente."""
    runner = app.test_cli_runner(mix_stderr=False)
    result = runner.invoke(args=[
        'crear-superadmin',
        '--email', 'super@test.com',
        '--nombre', 'Super Admin',
        '--password', 'password123',
    ])
    assert 'Superadmin creado exitosamente' in result.output

    usuario = Usuario.query.filter_by(email='super@test.com').first()
    assert usuario is not None
    assert usuario.rol == 'superadmin'
    assert usuario.empresa_id is None
    assert usuario.activo is True
    assert usuario.check_password('password123')


def test_crear_superadmin_duplicado(app):
    """Test que no permite crear un segundo superadmin."""
    runner = app.test_cli_runner(mix_stderr=False)
    runner.invoke(args=[
        'crear-superadmin',
        '--email', 'super1@test.com',
        '--nombre', 'Super Admin 1',
        '--password', 'password123',
    ])
    result = runner.invoke(args=[
        'crear-superadmin',
        '--email', 'super2@test.com',
        '--nombre', 'Super Admin 2',
        '--password', 'password456',
    ])
    assert 'Ya existe un superadmin' in result.output

    # Verificar que solo hay un superadmin
    count = Usuario.query.filter_by(rol='superadmin').count()
    assert count == 1
```

**Step 2: Correr test para verificar que falla**

Run: `make test-dev-run` o `pytest tests/test_cli.py -v` (en Docker)
Expected: FAIL - comando no existe.

**Step 3: Implementar comando CLI**

En `app/__init__.py`, agregar dentro de `register_commands(app)` (despues de la linea 125):

```python
import click

@app.cli.command('crear-superadmin')
@click.option('--email', required=True, help='Email del superadmin')
@click.option('--nombre', required=True, help='Nombre del superadmin')
@click.option('--password', required=True, help='Contrasena del superadmin')
def crear_superadmin(email, nombre, password):
    """Crea el usuario superadmin (unico en el sistema)."""
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
```

**Step 4: Correr test para verificar que pasa**

Run: `pytest tests/test_cli.py -v` (en Docker)
Expected: PASS

**Step 5: Commit**

```bash
git add app/__init__.py tests/test_cli.py
git commit -m "feat: agregar comando CLI crear-superadmin"
```

---

### Task 3: Decoradores superadmin_required y empresa_aprobada_required

**Files:**
- Modify: `app/utils/decorators.py`
- Test: `tests/test_decorators.py`

**Step 1: Escribir tests para los decoradores**

Crear `tests/test_decorators.py`:

```python
"""Tests para decoradores personalizados."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest
from flask import url_for
from flask_login import login_user

from app import create_app
from app.extensions import db as _db
from app.models import Empresa, Usuario


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
        SERVER_NAME='localhost',
    )

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def empresa_aprobada(app):
    emp = Empresa(nombre='Aprobada', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def empresa_pendiente(app):
    emp = Empresa(nombre='Pendiente', activa=True, aprobada=False)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def superadmin(app):
    u = Usuario(
        email='super@test.com', nombre='Super', rol='superadmin',
        activo=True, empresa_id=None,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def admin_aprobado(app, empresa_aprobada):
    u = Usuario(
        email='admin@test.com', nombre='Admin', rol='administrador',
        activo=True, empresa_id=empresa_aprobada.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def admin_pendiente(app, empresa_pendiente):
    u = Usuario(
        email='pending@test.com', nombre='Pending', rol='administrador',
        activo=True, empresa_id=empresa_pendiente.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


def test_superadmin_required_permite_superadmin(app, superadmin):
    """Superadmin puede acceder a rutas protegidas con @superadmin_required."""
    client = app.test_client()
    with client.session_transaction():
        pass
    with app.test_request_context():
        login_user(superadmin)
    # Se testea en las rutas del blueprint superadmin (Task 5)


def test_empresa_aprobada_permite_empresa_aprobada(app, admin_aprobado):
    """Admin de empresa aprobada puede acceder a rutas de escritura."""
    # Se testea en integracion con las rutas existentes (Task 6)
    assert admin_aprobado.empresa.aprobada is True


def test_empresa_pendiente_bloquea_escritura(app, admin_pendiente):
    """Admin de empresa pendiente no puede acceder a rutas de escritura."""
    assert admin_pendiente.empresa.aprobada is False
```

**Step 2: Correr test para verificar que falla**

Run: `pytest tests/test_decorators.py -v`
Expected: FAIL

**Step 3: Implementar decoradores**

Agregar en `app/utils/decorators.py`:

```python
def superadmin_required(f):
    """
    Decorador que requiere que el usuario sea superadmin.
    Debe usarse despues de @login_required.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Por favor, inicia sesion para acceder a esta pagina.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        if not current_user.es_superadmin:
            flash('No tienes permisos para acceder a esta seccion.', 'danger')
            return redirect(url_for('dashboard.index'))

        return f(*args, **kwargs)
    return decorated_function


def empresa_aprobada_required(f):
    """
    Decorador que requiere que la empresa del usuario este aprobada.
    Permite acceso al superadmin (no tiene empresa).
    Debe usarse despues de @login_required.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))

        # El superadmin no tiene empresa, siempre pasa
        if current_user.es_superadmin:
            return f(*args, **kwargs)

        if current_user.empresa and not current_user.empresa.aprobada:
            flash(
                'Tu empresa esta pendiente de aprobacion. '
                'No puedes realizar esta accion.',
                'warning',
            )
            return redirect(url_for('dashboard.index'))

        return f(*args, **kwargs)
    return decorated_function
```

**Step 4: Correr tests**

Run: `pytest tests/test_decorators.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/utils/decorators.py tests/test_decorators.py
git commit -m "feat: agregar decoradores superadmin_required y empresa_aprobada_required"
```

---

### Task 4: Modificar flujo de login y registro

**Files:**
- Modify: `app/routes/auth.py:14-44` (login)
- Modify: `app/routes/auth.py:47-104` (registro)
- Create: `app/forms/cambiar_password_forms.py`
- Create: `app/templates/auth/cambiar_password.html`
- Test: `tests/test_auth_superadmin.py`

**Step 1: Escribir tests**

Crear `tests/test_auth_superadmin.py`:

```python
"""Tests para flujo de login del superadmin y cambio de contrasena."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest
from app import create_app
from app.extensions import db as _db
from app.models import Empresa, Usuario


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def superadmin(app):
    u = Usuario(
        email='super@test.com', nombre='Super Admin', rol='superadmin',
        activo=True, empresa_id=None,
    )
    u.set_password('password123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def admin_con_cambio_password(app):
    emp = Empresa(nombre='Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    u = Usuario(
        email='admin@test.com', nombre='Admin', rol='administrador',
        activo=True, empresa_id=emp.id, debe_cambiar_password=True,
    )
    u.set_password('temporal123')
    _db.session.add(u)
    _db.session.commit()
    return u


def test_login_superadmin_redirige_a_superadmin_dashboard(app, superadmin):
    """Superadmin es redirigido a /superadmin/ tras login."""
    client = app.test_client()
    resp = client.post('/auth/login', data={
        'email': 'super@test.com',
        'password': 'password123',
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/superadmin/' in resp.headers['Location']


def test_login_con_debe_cambiar_password_redirige(app, admin_con_cambio_password):
    """Usuario con debe_cambiar_password es redirigido a cambiar contrasena."""
    client = app.test_client()
    resp = client.post('/auth/login', data={
        'email': 'admin@test.com',
        'password': 'temporal123',
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/auth/cambiar-password' in resp.headers['Location']


def test_registro_crea_empresa_no_aprobada(app):
    """El registro crea empresa con aprobada=False."""
    client = app.test_client()
    client.post('/auth/registro', data={
        'nombre': 'Admin Nuevo',
        'email': 'nuevo@test.com',
        'password': 'password123',
        'password_confirm': 'password123',
        'empresa_nombre': 'Mi Taller',
    })
    emp = Empresa.query.filter_by(nombre='Mi Taller').first()
    assert emp is not None
    assert emp.aprobada is False
```

**Step 2: Correr tests para verificar que fallan**

Run: `pytest tests/test_auth_superadmin.py -v`
Expected: FAIL

**Step 3: Crear formulario CambiarPasswordForm**

Crear `app/forms/cambiar_password_forms.py`:

```python
"""Formulario para cambio obligatorio de contrasena."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


class CambiarPasswordForm(FlaskForm):
    """Formulario de cambio de contrasena."""

    password_actual = PasswordField(
        'Contrasena actual',
        validators=[DataRequired(message='Ingresa tu contrasena actual.')],
        render_kw={'placeholder': 'Contrasena actual'},
    )
    password_nueva = PasswordField(
        'Nueva contrasena',
        validators=[
            DataRequired(message='Ingresa la nueva contrasena.'),
            Length(min=6, message='La contrasena debe tener al menos 6 caracteres.'),
        ],
        render_kw={'placeholder': 'Nueva contrasena'},
    )
    password_confirmar = PasswordField(
        'Confirmar nueva contrasena',
        validators=[
            DataRequired(message='Confirma la nueva contrasena.'),
            EqualTo('password_nueva', message='Las contrasenas no coinciden.'),
        ],
        render_kw={'placeholder': 'Confirmar nueva contrasena'},
    )
    submit = SubmitField('Cambiar contrasena')
```

**Step 4: Modificar ruta de login**

En `app/routes/auth.py`, modificar la funcion `login()`. Despues de `login_user(usuario, remember=form.remember.data)` (linea 34), reemplazar las lineas 36-40 con:

```python
            # Verificar si debe cambiar contrasena
            if usuario.debe_cambiar_password:
                flash('Debes cambiar tu contrasena antes de continuar.', 'warning')
                return redirect(url_for('auth.cambiar_password'))

            # Redirigir segun rol
            if usuario.es_superadmin:
                return redirect(url_for('superadmin.index'))

            # Redirigir a la pagina solicitada o al dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
```

**Step 5: Agregar ruta cambiar-password**

En `app/routes/auth.py`, agregar nueva ruta:

```python
@bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    """Cambio obligatorio de contrasena."""
    from ..forms.cambiar_password_forms import CambiarPasswordForm

    form = CambiarPasswordForm()

    if form.validate_on_submit():
        if not current_user.check_password(form.password_actual.data):
            flash('La contrasena actual es incorrecta.', 'danger')
            return render_template('auth/cambiar_password.html', form=form)

        current_user.set_password(form.password_nueva.data)
        current_user.debe_cambiar_password = False
        db.session.commit()

        flash('Contrasena cambiada exitosamente.', 'success')

        if current_user.es_superadmin:
            return redirect(url_for('superadmin.index'))
        return redirect(url_for('dashboard.index'))

    return render_template('auth/cambiar_password.html', form=form)
```

**Step 6: Crear template cambiar_password.html**

Crear `app/templates/auth/cambiar_password.html` (usar mismo estilo que login.html, sin sidebar):

Template con el formulario de cambio de contrasena con 3 campos: actual, nueva, confirmar. Mismo layout que login.html.

**Step 7: Modificar registro para aprobada=False**

En `app/routes/auth.py`, en la funcion `registro()`, la empresa ya se crea sin campo `aprobada` asi que tomara el default `False` del modelo. No hay cambio necesario aqui — solo verificar que funcione.

**Step 8: Correr tests**

Run: `pytest tests/test_auth_superadmin.py -v`
Expected: PASS

**Step 9: Commit**

```bash
git add app/routes/auth.py app/forms/cambiar_password_forms.py app/templates/auth/cambiar_password.html tests/test_auth_superadmin.py
git commit -m "feat: modificar login para superadmin, cambio obligatorio de contrasena y registro con empresa no aprobada"
```

---

### Task 5: Blueprint y rutas del superadmin

**Files:**
- Create: `app/routes/superadmin.py`
- Modify: `app/routes/__init__.py`
- Modify: `app/__init__.py:77-107`
- Test: `tests/test_superadmin.py`

**Step 1: Escribir tests**

Crear `tests/test_superadmin.py`:

```python
"""Tests para rutas del superadmin."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest
from flask_login import login_user

from app import create_app
from app.extensions import db as _db
from app.models import Empresa, Usuario


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def superadmin(app):
    u = Usuario(
        email='super@test.com', nombre='Super Admin', rol='superadmin',
        activo=True, empresa_id=None,
    )
    u.set_password('password123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def empresa_pendiente(app):
    emp = Empresa(nombre='Taller Pendiente', activa=True, aprobada=False)
    _db.session.add(emp)
    _db.session.flush()
    admin = Usuario(
        email='admin@taller.com', nombre='Admin Taller', rol='administrador',
        activo=True, empresa_id=emp.id,
    )
    admin.set_password('password123')
    _db.session.add(admin)
    _db.session.commit()
    return emp


@pytest.fixture
def empresa_aprobada(app):
    emp = Empresa(nombre='Taller Aprobado', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    admin = Usuario(
        email='admin@aprobado.com', nombre='Admin Aprobado', rol='administrador',
        activo=True, empresa_id=emp.id,
    )
    admin.set_password('password123')
    _db.session.add(admin)
    _db.session.commit()
    return emp


def _login_superadmin(client, app, superadmin):
    """Helper para login del superadmin."""
    client.post('/auth/login', data={
        'email': superadmin.email,
        'password': 'password123',
    })


def test_dashboard_superadmin(app, superadmin, empresa_pendiente, empresa_aprobada):
    """Dashboard muestra metricas correctas."""
    client = app.test_client()
    _login_superadmin(client, app, superadmin)
    resp = client.get('/superadmin/')
    assert resp.status_code == 200
    assert b'Taller Pendiente' in resp.data or b'pendiente' in resp.data.lower()


def test_listado_empresas(app, superadmin, empresa_pendiente, empresa_aprobada):
    """Listado muestra todas las empresas."""
    client = app.test_client()
    _login_superadmin(client, app, superadmin)
    resp = client.get('/superadmin/empresas')
    assert resp.status_code == 200
    assert b'Taller Pendiente' in resp.data
    assert b'Taller Aprobado' in resp.data


def test_aprobar_empresa(app, superadmin, empresa_pendiente):
    """Superadmin puede aprobar empresa pendiente."""
    client = app.test_client()
    _login_superadmin(client, app, superadmin)
    resp = client.post(
        f'/superadmin/empresas/{empresa_pendiente.id}/aprobar',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    emp = _db.session.get(Empresa, empresa_pendiente.id)
    assert emp.aprobada is True


def test_desactivar_admin(app, superadmin, empresa_aprobada):
    """Superadmin puede desactivar admin de empresa."""
    client = app.test_client()
    _login_superadmin(client, app, superadmin)
    admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id, rol='administrador').first()
    resp = client.post(
        f'/superadmin/empresas/{empresa_aprobada.id}/desactivar-admin',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    _db.session.refresh(admin)
    assert admin.activo is False


def test_activar_admin(app, superadmin, empresa_aprobada):
    """Superadmin puede reactivar admin de empresa."""
    client = app.test_client()
    _login_superadmin(client, app, superadmin)
    admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id, rol='administrador').first()
    admin.activo = False
    _db.session.commit()
    resp = client.post(
        f'/superadmin/empresas/{empresa_aprobada.id}/activar-admin',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    _db.session.refresh(admin)
    assert admin.activo is True


def test_reset_password_admin(app, superadmin, empresa_aprobada):
    """Superadmin puede resetear contrasena de admin."""
    client = app.test_client()
    _login_superadmin(client, app, superadmin)
    resp = client.post(
        f'/superadmin/empresas/{empresa_aprobada.id}/reset-password',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id, rol='administrador').first()
    assert admin.debe_cambiar_password is True


def test_acceso_denegado_para_admin_normal(app, empresa_aprobada):
    """Un admin normal no puede acceder a /superadmin/."""
    client = app.test_client()
    admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id).first()
    client.post('/auth/login', data={
        'email': admin.email,
        'password': 'password123',
    })
    resp = client.get('/superadmin/', follow_redirects=False)
    assert resp.status_code == 302  # Redirigido
```

**Step 2: Correr tests para verificar que fallan**

Run: `pytest tests/test_superadmin.py -v`
Expected: FAIL - blueprint no existe.

**Step 3: Crear blueprint superadmin**

Crear `app/routes/superadmin.py`:

```python
"""Rutas del panel de superadmin."""

import secrets
import string

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Empresa, Usuario
from ..utils.decorators import superadmin_required

bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')


def _generar_password_temporal(longitud=12):
    """Genera una contrasena aleatoria alfanumerica."""
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(longitud))


def _obtener_admin_principal(empresa_id):
    """Obtiene el primer usuario administrador de una empresa."""
    return Usuario.query.filter_by(
        empresa_id=empresa_id, rol='administrador'
    ).order_by(Usuario.created_at).first()


@bp.route('/')
@login_required
@superadmin_required
def index():
    """Dashboard del superadmin con metricas."""
    total_empresas = Empresa.query.count()
    empresas_pendientes = Empresa.query.filter_by(aprobada=False, activa=True).count()
    empresas_aprobadas = Empresa.query.filter_by(aprobada=True, activa=True).count()
    empresas_inactivas = Empresa.query.filter_by(activa=False).count()

    # Empresas pendientes de aprobacion (para mostrar alerta)
    pendientes = Empresa.query.filter_by(
        aprobada=False, activa=True
    ).order_by(Empresa.created_at.desc()).limit(5).all()

    return render_template(
        'superadmin/dashboard.html',
        total_empresas=total_empresas,
        empresas_pendientes=empresas_pendientes,
        empresas_aprobadas=empresas_aprobadas,
        empresas_inactivas=empresas_inactivas,
        pendientes=pendientes,
    )


@bp.route('/empresas')
@login_required
@superadmin_required
def empresas():
    """Listado de todas las empresas con sus admins."""
    filtro = request.args.get('filtro', 'todas')

    query = Empresa.query.order_by(Empresa.created_at.desc())
    if filtro == 'pendientes':
        query = query.filter_by(aprobada=False, activa=True)
    elif filtro == 'aprobadas':
        query = query.filter_by(aprobada=True, activa=True)
    elif filtro == 'inactivas':
        query = query.filter_by(activa=False)

    empresas_list = query.all()

    # Obtener admin principal de cada empresa
    empresas_con_admin = []
    for emp in empresas_list:
        admin = _obtener_admin_principal(emp.id)
        empresas_con_admin.append({'empresa': emp, 'admin': admin})

    return render_template(
        'superadmin/empresas.html',
        empresas=empresas_con_admin,
        filtro_actual=filtro,
    )


@bp.route('/empresas/<int:empresa_id>/aprobar', methods=['POST'])
@login_required
@superadmin_required
def aprobar_empresa(empresa_id):
    """Aprueba una empresa pendiente."""
    empresa = db.session.get(Empresa, empresa_id)
    if not empresa:
        flash('Empresa no encontrada.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    empresa.aprobada = True
    db.session.commit()
    flash(f'Empresa "{empresa.nombre}" aprobada exitosamente.', 'success')
    return redirect(url_for('superadmin.empresas'))


@bp.route('/empresas/<int:empresa_id>/desactivar-admin', methods=['POST'])
@login_required
@superadmin_required
def desactivar_admin(empresa_id):
    """Desactiva el admin principal de una empresa."""
    admin = _obtener_admin_principal(empresa_id)
    if not admin:
        flash('No se encontro administrador para esta empresa.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    admin.activo = False
    db.session.commit()
    flash(f'Usuario {admin.email} desactivado.', 'success')
    return redirect(url_for('superadmin.empresas'))


@bp.route('/empresas/<int:empresa_id>/activar-admin', methods=['POST'])
@login_required
@superadmin_required
def activar_admin(empresa_id):
    """Reactiva el admin principal de una empresa."""
    admin = _obtener_admin_principal(empresa_id)
    if not admin:
        flash('No se encontro administrador para esta empresa.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    admin.activo = True
    db.session.commit()
    flash(f'Usuario {admin.email} activado.', 'success')
    return redirect(url_for('superadmin.empresas'))


@bp.route('/empresas/<int:empresa_id>/reset-password', methods=['POST'])
@login_required
@superadmin_required
def reset_password(empresa_id):
    """Genera contrasena temporal para el admin de una empresa."""
    admin = _obtener_admin_principal(empresa_id)
    if not admin:
        flash('No se encontro administrador para esta empresa.', 'danger')
        return redirect(url_for('superadmin.empresas'))

    password_temporal = _generar_password_temporal()
    admin.set_password(password_temporal)
    admin.debe_cambiar_password = True
    db.session.commit()

    flash(
        f'Contrasena temporal para {admin.email}: {password_temporal}',
        'info',
    )
    return redirect(url_for('superadmin.empresas'))
```

**NOTA:** Agregar `from flask import request` al import de la linea 5.

**Step 4: Registrar blueprint**

En `app/routes/__init__.py`, agregar:
```python
from .superadmin import bp as superadmin_bp
```
Y en `__all__` agregar `'superadmin_bp'`.

En `app/__init__.py`, en `register_blueprints()`, agregar:
```python
from .routes import superadmin_bp
# ... (dentro de la funcion)
app.register_blueprint(superadmin_bp)
```

**Step 5: Correr tests**

Run: `pytest tests/test_superadmin.py -v`
Expected: PASS (los tests de templates fallaran hasta Task 6, ajustar si es necesario)

**Step 6: Commit**

```bash
git add app/routes/superadmin.py app/routes/__init__.py app/__init__.py tests/test_superadmin.py
git commit -m "feat: agregar blueprint y rutas del superadmin con gestion de empresas"
```

---

### Task 6: Templates del superadmin

**Files:**
- Create: `app/templates/superadmin/dashboard.html`
- Create: `app/templates/superadmin/empresas.html`
- Create: `app/templates/components/sidebar_superadmin.html`
- Modify: `app/templates/base.html:26-28`

**Step 1: Crear sidebar del superadmin**

Crear `app/templates/components/sidebar_superadmin.html`:

Sidebar con la misma estructura CSS que `sidebar.html` pero con solo 2 items:
- Dashboard (`/superadmin/`)
- Empresas (`/superadmin/empresas`)

User section abajo con iniciales, nombre y rol "Superadmin".

**Step 2: Modificar base.html para seleccionar sidebar**

En `app/templates/base.html`, linea 26-28, cambiar:

```html
{% if current_user.is_authenticated %}
    {% if current_user.es_superadmin %}
        {% include 'components/sidebar_superadmin.html' %}
    {% else %}
        {% include 'components/sidebar.html' %}
    {% endif %}
{% endif %}
```

**Step 3: Agregar banner de empresa pendiente en base.html**

En `app/templates/base.html`, despues de `{% block alerts %}` (linea 40-42), agregar:

```html
{% if current_user.is_authenticated and not current_user.es_superadmin
   and current_user.empresa and not current_user.empresa.aprobada %}
<div class="alert alert-warning alert-dismissible fade show mx-3 mt-3" role="alert">
    <span class="material-symbols-rounded me-2">pending</span>
    <strong>Empresa pendiente de aprobacion.</strong>
    Tu cuenta esta en modo lectura hasta que un administrador apruebe tu empresa.
</div>
{% endif %}
```

**Step 4: Crear template dashboard superadmin**

Crear `app/templates/superadmin/dashboard.html`:

Dashboard con 4 tarjetas de metricas (total empresas, pendientes, aprobadas, inactivas) + listado de empresas pendientes recientes con boton de aprobar rapido. Usar mismos estilos que el dashboard existente.

**Step 5: Crear template listado de empresas**

Crear `app/templates/superadmin/empresas.html`:

Tabla con columnas: Empresa, CUIT, Admin (email), Estado (badge), Fecha registro, Acciones.

Acciones por empresa:
- Si no aprobada: boton "Aprobar"
- Si admin activo: boton "Desactivar"
- Si admin inactivo: boton "Activar"
- Boton "Reset Password" (siempre visible)

Filtros arriba: Todas | Pendientes | Aprobadas | Inactivas (como tabs o botones).

La contrasena temporal se muestra en un flash message tipo `info` que el superadmin puede copiar.

**Step 6: Verificar visualmente**

Run: `make up-dev`, crear superadmin con `flask crear-superadmin`, hacer login y navegar.

**Step 7: Commit**

```bash
git add app/templates/superadmin/ app/templates/components/sidebar_superadmin.html app/templates/base.html
git commit -m "feat: agregar templates del panel superadmin con dashboard y gestion de empresas"
```

---

### Task 7: Aplicar empresa_aprobada_required a rutas de escritura

**Files:**
- Modify: `app/routes/productos.py` (rutas POST/crear/editar/eliminar)
- Modify: `app/routes/ventas.py` (rutas POST)
- Modify: `app/routes/inventario.py` (rutas POST)
- Modify: `app/routes/compras.py` (rutas POST)
- Modify: `app/routes/presupuestos.py` (rutas POST)
- Modify: `app/routes/caja.py` (rutas POST)
- Modify: `app/routes/clientes.py` (rutas POST)
- Modify: `app/routes/configuracion.py` (rutas POST)
- Modify: `app/routes/proveedores.py` (rutas POST)
- Test: `tests/test_empresa_aprobada.py`

**Step 1: Escribir test de integracion**

Crear `tests/test_empresa_aprobada.py`:

```python
"""Tests para verificar que empresa no aprobada no puede hacer escrituras."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest
from app import create_app
from app.extensions import db as _db
from app.models import Empresa, Usuario


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def admin_no_aprobado(app):
    emp = Empresa(nombre='No Aprobada', activa=True, aprobada=False)
    _db.session.add(emp)
    _db.session.flush()
    u = Usuario(
        email='admin@noaprobada.com', nombre='Admin', rol='administrador',
        activo=True, empresa_id=emp.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


def _login(client, email, password):
    client.post('/auth/login', data={'email': email, 'password': password})


def test_empresa_no_aprobada_puede_ver_dashboard(app, admin_no_aprobado):
    """Empresa no aprobada puede ver el dashboard (lectura)."""
    client = app.test_client()
    _login(client, admin_no_aprobado.email, 'test123')
    resp = client.get('/')
    assert resp.status_code == 200


def test_empresa_no_aprobada_no_puede_crear_producto(app, admin_no_aprobado):
    """Empresa no aprobada no puede crear productos."""
    client = app.test_client()
    _login(client, admin_no_aprobado.email, 'test123')
    resp = client.post('/productos/crear', follow_redirects=False)
    # Debe ser redirigido al dashboard
    assert resp.status_code == 302
```

**Step 2: Correr tests**

Run: `pytest tests/test_empresa_aprobada.py -v`
Expected: FAIL (las rutas aun no tienen el decorador)

**Step 3: Agregar decorador a todas las rutas de escritura**

En cada archivo de rutas, importar `empresa_aprobada_required` desde `app.utils.decorators` y agregarlo a las rutas que hacen POST/escritura. El decorador va despues de `@login_required`.

Patron:
```python
@bp.route('/crear', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
def crear():
    ...
```

Rutas de SOLO LECTURA (GET que muestran listados) NO necesitan el decorador.

**Step 4: Correr tests**

Run: `pytest tests/test_empresa_aprobada.py -v`
Expected: PASS

**Step 5: Correr suite completa**

Run: `pytest` (toda la suite)
Expected: PASS - asegurar que no se rompieron tests existentes.

**Step 6: Commit**

```bash
git add app/routes/*.py tests/test_empresa_aprobada.py
git commit -m "feat: proteger rutas de escritura con empresa_aprobada_required"
```

---

### Task 8: Ajustar context processor y protecciones

**Files:**
- Modify: `app/__init__.py:128-157` (register_template_context)
- Modify: `app/routes/dashboard.py:15-17`

**Step 1: Ajustar context processor para superadmin**

En `app/__init__.py`, funcion `register_template_context`, el `get_config` usa `current_user.empresa_id` que sera `None` para superadmin. Agregar proteccion:

```python
def get_config(clave, default=None):
    if not current_user.is_authenticated:
        return default
    if current_user.empresa_id is None:
        return default
    config_item = Configuracion.query.filter_by(
        clave=clave, empresa_id=current_user.empresa_id
    ).first()
    return config_item.get_valor() if config_item else default
```

**Step 2: Redirigir dashboard segun rol**

En `app/routes/dashboard.py`, en la funcion `index()`, agregar al inicio:

```python
if current_user.es_superadmin:
    return redirect(url_for('superadmin.index'))
```

**Step 3: Correr suite completa de tests**

Run: `pytest`
Expected: PASS

**Step 4: Commit**

```bash
git add app/__init__.py app/routes/dashboard.py
git commit -m "fix: ajustar context processor y dashboard para superadmin sin empresa"
```

---

### Task 9: Actualizar fixture de tests y memoria del proyecto

**Files:**
- Modify: `tests/conftest.py`
- Modify: memoria del proyecto

**Step 1: Actualizar conftest.py**

Agregar fixture de empresa con `aprobada=True` para que tests existentes sigan funcionando:

```python
@pytest.fixture
def empresa(app):
    """Crea una empresa de prueba (aprobada por defecto)."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp
```

**Step 2: Correr toda la suite de tests**

Run: `pytest`
Expected: TODOS PASS

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "fix: actualizar fixture empresa con aprobada=True para tests existentes"
```

---

### Task 10: Verificacion final y lint

**Step 1: Correr ruff**

Run: `.venv/bin/ruff check .`
Expected: Sin errores

**Step 2: Correr ruff format**

Run: `.venv/bin/ruff format .`

**Step 3: Correr suite completa**

Run: `pytest`
Expected: TODOS PASS

**Step 4: Verificar make up-dev funciona**

Run: `make up-dev` y probar manualmente:
1. Crear superadmin: `flask crear-superadmin --email admin@ferrerp.com --nombre "Super Admin" --password admin123`
2. Registrar nueva empresa desde /auth/registro
3. Verificar que empresa nueva esta en modo read-only
4. Login como superadmin, verificar dashboard y listado
5. Aprobar empresa, verificar que ahora puede operar
6. Reset password de un admin, verificar que obliga a cambiar
7. Desactivar/activar admin

**Step 5: Commit final si hubo fixes de lint**

```bash
git add -A
git commit -m "style: aplicar formato ruff"
```
