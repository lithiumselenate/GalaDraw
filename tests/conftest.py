import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest

import app as gala


@pytest.fixture
def app():
    gala.AUTH_ENABLED = False
    gala.app.config.update(TESTING=True)
    with gala.app.app_context():
        gala.db.drop_all()
        gala.db.create_all()
        gala.seed_auth_data()
    yield gala.app
    gala.AUTH_ENABLED = False


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def module():
    return gala


def login(client, username="superadmin", password="Changeme123!"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


@pytest.fixture
def login_as_superadmin():
    return login
