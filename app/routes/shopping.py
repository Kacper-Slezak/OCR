from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList
from app.models import Receipt

shopping_bp = Blueprint('shopping', __name__, url_prefix='/shopping')

@shopping_bp.route('/', methods=['GET'])
@login_required
def shopping_dashboard():
    user_lists = ShoppingList.query.filter_by(owner_id=current_user.id).all()
    return render_template('shopping/dashboard.html', lists=user_lists)
