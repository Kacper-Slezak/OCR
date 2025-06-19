# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os

# Utwórz instancje rozszerzeń poza funkcją, aby były dostępne globalnie
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    migrate = Migrate(app, db)

    # Ustawianie widoku dla niezalogowanych użytkowników
    login_manager.login_view = 'auth.login' # Załóżmy, że masz Blueprint 'auth' z logowaniem
    login_manager.login_message_category = 'info'
    login_manager.login_message = 'Wymagane logowanie, aby korzystać ze strony.'

    # Importowanie blueprints
    # Ważne: importujemy MODUŁ, w którym zdefiniowany jest Blueprint,
    # a NIE bezpośrednio funkcje czy serwisy z innych podkatalogów.
    from .routes import auth  # Importuj Blueprint 'auth' (jeśli istnieje)
    from .routes import ocr   # <-- TYLKO TEN IMPORT JEST POTRZEBNY DLA OCR ROUTINGU

    # Rejestrowanie blueprints w aplikacji
    app.register_blueprint(auth.bp) # Zarejestruj auth blueprint
    app.register_blueprint(ocr.bp)   # Zarejestruj ocr blueprint

    # Funkcja user_loader dla Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        # Importujemy model User Wewnątrz tej funkcji,
        # aby uniknąć cyklicznych zależności importów (app.py importuje models.py, a models.py potrzebuje db z app.py)
        from app.models import User
        return User.query.get(int(user_id))

    with app.app_context():
        # Tutaj możesz dodać `db.create_all()` jeśli nie używasz Flask-Migrate
        # Jeśli używasz Flask-Migrate, to `flask db upgrade` tworzy tabele
        pass

    return app