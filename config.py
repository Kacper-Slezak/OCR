# config.py
import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    # Lepsza praktyka: Jeśli chcesz wymusić definicję w .env, usuń fallback
    SECRET_KEY            = os.getenv('SECRET_KEY')
    SECURITY_PASSWORD_SALT= os.getenv('SECURITY_PASSWORD_SALT')
    # Dla bazy danych fallback może zostać, jeśli domyślne sqlite jest ok
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Konfiguracja dla Flask-Mail - usunięcie fallbacków, aby wymusić definicję w .env
    MAIL_SERVER         = os.getenv('EMAIL_HOST')
    MAIL_PORT           = int(os.getenv('EMAIL_PORT', 587))
    MAIL_USE_TLS        = os.getenv('EMAIL_USE_TLS', 'False').lower() in ('true','1','yes')
    MAIL_USE_SSL        = False
    MAIL_USERNAME       = os.getenv('EMAIL_USER')
    MAIL_PASSWORD       = os.getenv('EMAIL_PASS')
    MAIL_DEFAULT_SENDER = os.getenv('EMAIL_DEFAULT_SENDER', os.getenv('EMAIL_USER'))

    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # TESSERACT_PATH - usunięcie fallbacka, aby wymusić definicję w .env
    TESSERACT_PATH = os.environ.get('TESSERACT_PATH')

    # Poprawiona ścieżka do katalogu tymczasowego Tesseracta
    TESSERACT_TEMP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'temp_tesseract_output')