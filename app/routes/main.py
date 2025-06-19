# app/routes/main.py
from flask import Blueprint, redirect, url_for
from flask_login import current_user

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('ocr.list_receipts'))
    else:
        return redirect(url_for('auth.login'))

# Możesz tu dodać inne trasy, np. dla statycznych stron "O nas", "Kontakt", jeśli kiedyś je zrobisz
# @bp.route('/about')
# def about():
#     return render_template('main/about.html')