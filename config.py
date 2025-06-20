# config.py
import os

class Config:
    # Lepsza praktyka: Jeśli chcesz wymusić definicję w .env, usuń fallback
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # Dla bazy danych fallback może zostać, jeśli domyślne sqlite jest ok
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Konfiguracja dla Flask-Mail - usunięcie fallbacków, aby wymusić definicję w .env
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT')) if os.environ.get('MAIL_PORT') else 587 # Bezpieczniejsze konwertowanie int
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') == 'True' # Bardziej jednoznaczna konwersja do bool
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # TESSERACT_PATH - usunięcie fallbacka, aby wymusić definicję w .env
    TESSERACT_PATH = os.environ.get('TESSERACT_PATH')

    # Poprawiona ścieżka do katalogu tymczasowego Tesseracta
    TESSERACT_TEMP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'temp_tesseract_output')