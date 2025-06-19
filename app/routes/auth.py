import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, db

bp = Blueprint('auth', __name__, url_prefix='/auth')

#-- Logowanie --
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('base.html'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Zalogowano.')
            return redirect(url_for('base.html'))
        else:
            flash('Nieprawidłowy mail lub hasło.')
            return redirect(url_for('bp.login'))
    return render_template('auth/login.html')

#-- Rejestracja --
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash("Podano różne hasła. Proszę spróbować ponownie.")
            return redirect(url_for('bp.register'))

        if User.query.filter_by(username=username).first() and User.query.filter_by(email=email).first():
            flash('Użytkownik już istnieje')
            return redirect(url_for('bp.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username = username, email = email, password_hashed = hashed_password)

        db.session.add(new_user)
        db.session.commit()
        flash('Rejestracja zakończona sukcesem. Możesz się zalogować.')
        return redirect(url_for('bp.login'))

    return render_template('auth/register.html')

#-- Wylogowanie --
@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Wylogowano')
    return redirect(url_for('bp.login'))