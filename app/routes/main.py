# app/routes/main.py
from flask import Blueprint, redirect, url_for, render_template
from flask_login import current_user, login_required

from app import db
from app.models import ShoppingList

bp = Blueprint('main', __name__)

@bp.route('/', methods=['GET'])
@login_required
def dashboard():
    user_recipts = ShoppingList.query.filter_by(created_by=current_user.id).all()
    return render_template('main/dashboard.html', recipts=user_recipts)

# Możesz tu dodać inne trasy, np. dla statycznych stron "O nas", "Kontakt", jeśli kiedyś je zrobisz
# @bp.route('/about')
# def about():
#     return render_template('main/about.html')