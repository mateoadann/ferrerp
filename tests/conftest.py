import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=True,
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
