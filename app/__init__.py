# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()

login_manager.login_view = 'auth.login'

def create_app():
    app = Flask(__name__)

    # Załadowanie konfiguracji
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)

    migrate = Migrate(app, db)

    # --- PONIŻSZE SEKCJE SĄ NA RAZIE ZAKOMENTOWANE ---
    # Odkomentuj je, gdy odpowiednie pliki route'ów (blueprinty) zostaną stworzone

    # from .routes import auth # Martyna
    # from .routes import shopping # Tymon
    # from .routes import ocr # Martyna/Kacper
    # from .routes import settlements # Tymon
    # from .routes import notifications # Kiryl

    # app.register_blueprint(auth.bp)
    # app.register_blueprint(shopping.bp)
    # app.register_blueprint(ocr.bp)
    # app.register_blueprint(settlements.bp)
    # app.register_blueprint(notifications.bp)

    # Kontekst aplikacji dla operacji bazodanowych.
    # W trybie deweloperskim możesz tymczasowo odkomentować 'db.create_all()',
    # aby szybko utworzyć tabele, ale w środowisku produkcyjnym UŻYWAJ WYŁĄCZNIE MIGRACJI!
    with app.app_context():
        # db.create_all() # ODkomentuj TYLKO do szybkiego testu na DEV, potem ZAKOMENTUJ/USUŃ!
        pass

    return app
