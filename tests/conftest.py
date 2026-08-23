import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from config import Config
from app import create_app
from extensions import db as _db


@pytest.fixture()
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
        WTF_CSRF_ENABLED = False  # los tests envían forms directamente, sin JS
        MAIL_ENABLED = False  # nunca se envían correos reales en tests
        SESSION_COOKIE_SECURE = False
        RATELIMIT_ENABLED = False
        ADMIN_EMAIL = ""
        ADMIN_PASSWORD = ""

    application = create_app(TestConfig)
    with application.app_context():
        yield application
        _db.session.remove()
        _db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()
