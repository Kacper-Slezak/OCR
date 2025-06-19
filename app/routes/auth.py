import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required
from app.models import User, db

auth = Blueprint('auth', __name__)

#-- Logowanie --
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.get['username']
        password = request.get['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Zalogowano.')
            return redirect(url_for('main.home'))
        else:
            flash('Nieprawidłowy mail lub hasło.')
            return redirect(url_for('auth.login'))
        return render_template(login.html)

#-- Rejestracja --
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Podano różne hasła. Proszę spróbować ponownie.")
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first() & User.query.filter_by(email=email).first():
            flash('Użytkownik już istnieje')
            return redirect(url_for('auth.register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password)

        db.session.add(new_user)
        db.session.commit()
        flash('Rejestracja zakończona sukcesem. Możesz się zalogować.')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

#-- Wylogowanie --
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Wylogowano')
    return redirect(url_for('auth.login'))
