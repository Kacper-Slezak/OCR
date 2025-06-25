# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import os


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
    # Sciezka do katalogu, w którym znajduje się ten plik (__init__.py), czyli 'app/'
    current_dir = os.path.dirname(__file__)
    # Sciezka do katalogu nadrzędnego (czyli katalogu projektu 'OCR')
    # To jest ten katalog, w którym znajduje się 'templates/' i 'app/'
    project_root_dir = os.path.abspath(os.path.join(current_dir, '..'))

    # Inicjalizacja aplikacji Flask, wskazując DOKŁADNĄ ścieżkę do folderu templates
    app = Flask(__name__,
                instance_relative_config=True,
                template_folder=os.path.join(project_root_dir, 'templates') # <--- DODAJ TĘ LINIĘ
               )
    app.config.from_object('config.Config')

    # Konfiguracja bazy danych
    app.config['SQLALCHEMY_DATABASE_URL'] = os.getenv('DATABASE_URL')

    # Konfiguracja serwera SMTP dla Flask-Mail
    app.config['MAIL_SERVER']   = os.getenv('EMAIL_HOST')
    app.config['MAIL_PORT']     = int(os.getenv('EMAIL_PORT', 587))
    app.config['MAIL_USE_TLS']  = True
    app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
    app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')

    db.init_app(app)
    login_manager.init_app(app)
    migrate = Migrate(app, db) # Tutaj możesz też przekazać app do Migrate od razu

    mail.init_app(app)
    scheduler.start

    # Ustawianie widoku dla niezalogowanych użytkowników
    login_manager.login_view = 'auth.login' # Załóżmy, że masz Blueprint 'auth' z logowaniem
    login_manager.login_message_category = 'info'
    login_manager.login_message = 'Wymagane logowanie, aby korzystać ze strony.'

    # Importowanie blueprints
    from .routes import auth
    from .routes import ocr


    from .routes.main import bp as main_bp
    from .routes.receipt import receipt_bp
    from .routes import settlements  # <-- DODAJ TEN IMPORT
    from app.routes.notifications import notifications_bp
    # Rejestrowanie blueprints w aplikacji
    app.register_blueprint(auth.bp) # Zarejestruj auth blueprint
    app.register_blueprint(ocr.bp)   # Zarejestruj ocr blueprint
    app.register_blueprint(main_bp)

    app.register_blueprint(receipt_bp)
    app.register_blueprint(settlements.bp)  #

    # Rejestracja blueprintu powiadomień
    app.register_blueprint(notifications_bp)

    # Harmonogram wysyłania wiadomości przypomniających
    from app.services.notifications_services import wyslij_przypomnienia_dluznikom
    scheduler.add_job(
        func=wyslij_przypomnienia_dluznikom,
        trigger='cron',
        hour=9,
        minute=0,
        id='przypomnienia_dluznikom'
    )
    scheduler.start()


    # Funkcja user_loader dla Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
        pass

    return app
