# app/routes/main.py
from flask import Blueprint, redirect, url_for, render_template
from flask_login import current_user, login_required

from app import db
from app.models import ShoppingList
from app.models import Receipt

bp = Blueprint('main', __name__)

@bp.route('/', methods=['GET'])
@login_required
def home():
    user_recipts = ShoppingList.query.filter_by(owner_id=current_user.id).all()
    return render_template('app/dashboard.html', recipts=user_recipts)

# Możesz tu dodać inne trasy, np. dla statycznych stron "O nas", "Kontakt", jeśli kiedyś je zrobisz
# @bp.route('/about')
# def about():
#     return render_template('main/about.html')