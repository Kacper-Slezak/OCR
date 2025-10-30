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

# <--- POPRAWKA: Dodano brakującą funkcję start_scheduler
def start_scheduler(app):
    """Uruchamia zadania w tle (wymagane przez gunicorn.conf.py)."""
    
    # Importujemy zadanie, które ma być uruchamiane
    from app.services.notifications_services import wyslij_przypomnienia_dluznikom
    
    if not scheduler.running:
        # Używamy app.app_context() w zadaniu, aby miało dostęp do konfiguracji i DB
        @scheduler.scheduled_job('interval', hours=24) # Uruchom np. raz na 24 godziny
        def scheduled_task_wrapper():
            with app.app_context():
                print("Scheduler: Uruchamiam zaplanowane zadanie (wyslij_przypomnienia_dluznikom)...")
                wyslij_przypomnienia_dluznikom()
        
        scheduler.start()
        print("Scheduler został pomyślnie uruchomiony.")
        # Zarejestruj zamknięcie schedulera przy wyjściu z aplikacji
        atexit.register(lambda: scheduler.shutdown())

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
    
    # <--- POPRAWKA: Rejestrowanie blueprints w aplikacji (brakowało tego)
    app.register_blueprint(auth.bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(receipt_bp)
    app.register_blueprint(settlements.bp)
    app.register_blueprint(notifications_bp)

    # <--- POPRAWKA: Funkcja musi zwracać instancję aplikacji
    return app