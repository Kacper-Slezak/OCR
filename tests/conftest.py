# tests/conftest.py
import pytest
from sqlalchemy.orm import scoped_session, sessionmaker
from app import create_app, db
from app.models import User

@pytest.fixture(scope='session')
def app():
    """Tworzy instancję aplikacji Flask skonfigurowaną do testowania."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "LOGIN_DISABLED": True
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Udostępnia testowego klienta HTTP."""
    return app.test_client()

@pytest.fixture(scope='function')
def runner(app):
    """Udostępnia testowego runnera CLI."""
    return app.test_cli_runner()

@pytest.fixture(scope='function')
def session(app):
    """Tworzy czystą sesję bazy danych dla każdego testu."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()

        session_factory = sessionmaker(bind=connection)
        scoped = scoped_session(session_factory)

        db.session = scoped

        try:
            yield scoped
        finally:
            transaction.rollback()
            connection.close()
            scoped.remove()

@pytest.fixture
def test_user(session):
    """Tworzy i zapisuje użytkownika testowego."""
    user = User(username='testuser', email='test@example.com')
    user.set_password('password')
    session.add(user)
    session.commit()
    return user
