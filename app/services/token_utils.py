# app/services/token_utils.py

from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def generate_confirmation_token(email):
    """Generuje token do resetowania hasła."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

def confirm_token(token, expiration=3600):
    """
    Sprawdza token. Zwraca email lub False, jeśli niepoprawny.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except Exception:
        return False
    return email
