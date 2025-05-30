from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Zaloguj się, aby uzyskać dostęp do tej strony.'
    login_manager.login_message_category = 'info'

    from app.routes.auth import bp as auth_bp
    from app.routes.main import bp as main_bp
    from app.routes.shopping import bp as shopping_bp
    from app.routes.ocr import bp as ocr_bp
    from app.routes.settlements import bp as settlements_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(shopping_bp, url_prefix='/shopping')
    app.register_blueprint(ocr_bp, url_prefix='/ocr')
    app.register_blueprint(settlements_bp, url_prefix='/settlements')

    return app