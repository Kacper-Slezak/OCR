# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import os
import atexit
from datetime import datetime
import logging

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

# Utwórz instancje rozszerzeń poza funkcją, aby były dostępne globalnie
db = SQLAlchemy()
login_manager = LoginManager()

# Zmienne dla mailow
mail = Mail()
scheduler = BackgroundScheduler()

def create_app():
    # Ładowanie zmiennych środowiskowych z .env
    load_dotenv()
    # Definiowanie ścieżek
    current_dir = os.path.dirname(__file__)
    project_root_dir = os.path.abspath(os.path.join(current_dir, '..'))

    # Inicjalizacja aplikacji Flask
    app = Flask(__name__,
                instance_relative_config=True,
                template_folder=os.path.join(project_root_dir, 'templates')
               )
    app.config.from_object('config.Config')

    # Konfiguracja serwera SMTP dla Flask-Mail
    app.config['MAIL_SERVER']   = os.getenv('EMAIL_HOST')
    app.config['MAIL_PORT']     = int(os.getenv('EMAIL_PORT', 587))
    app.config['MAIL_USE_TLS']  = True
    app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
    app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')

    db.init_app(app)
    login_manager.init_app(app)
    migrate = Migrate(app, db) 

    mail.init_app(app)

    # Ustawianie widoku dla niezalogowanych użytkowników
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.login_message = 'Wymagane logowanie, aby korzystać ze strony.'

    # --- STARY KOD SCHEDULERA ZOSTAŁ STĄD USUNIĘTY ---

    # Importowanie blueprints
    from .routes import auth
    from .routes.main import bp as main_bp
    from .routes.receipt import receipt_bp
    from .routes import settlements
    from app.routes.notifications import notifications_bp
    
    # Rejestrowanie blueprints w aplikacji
    app