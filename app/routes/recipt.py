from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList
from app.models import Receipt

recipt_bp = Blueprint('shopping', __name__, url_prefix='/recipt')

@recipt_bp.route('/<int:recipt_id>', methods=['GET'])
@login_required
def recipt(receipt_id):
    current_receipt = Receipt.query.filter_by(id=receipt_id, user_id=current_user.id).first_or_404()
    parsed_data = current_receipt.get_processed_data()
    return render_template('app/recipt.html', receipt=current_receipt, parsed_data=parsed_data)