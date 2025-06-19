# app/routes/main.py

from flask import Blueprint, render_template

bp = Blueprint('main', __name__)   # ← здесь именно имя bp
@bp.route('/')
def index():
    return render_template('index.html')
