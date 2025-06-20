import bcrypt  # Możesz usunąć, jeśli używasz werkzeug.security
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, db  # Upewnij się, że User i db są zaimportowane
from app.forms import LoginForm, RegistrationForm  # <--- KLUCZOWY IMPORT FORMULARZY WTFORMS

bp = Blueprint('auth', __name__, url_prefix='/auth')


# Główna trasa dla /auth - przekierowuje na /auth/login
# (Jeśli masz Blueprint 'main' dla '/', to ta trasa na /auth/ będzie używana tylko, gdy ktoś wejdzie bezpośrednio na /auth)
@bp.route('/')
def auth_index():
    return redirect(url_for('auth.login'))


# -- Logowanie --
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Zmieniono 'base.html' na 'ocr.list_receipts' jako stronę po zalogowaniu
        # lub na 'main.index' jeśli masz główną stronę po zalogowaniu
        return redirect(url_for('main.dashboard'))  # Domyślna strona po zalogowaniu

    form = LoginForm()  # <--- INICJALIZACJA FORMULARZA WTFORMS

    if form.validate_on_submit():  # <--- Użycie walidacji WTForms
        username_or_email = form.username_or_email.data
        password = form.password.data
        remember = form.remember_me.data

        # Sprawdzanie, czy to nazwa użytkownika czy email
        user = User.query.filter_by(username=username_or_email).first()
        if not user:  # Jeśli nie znaleziono po nazwie użytkownika, spróbuj po emailu
            user = User.query.filter_by(email=username_or_email).first()

        if user and check_password_hash(user.password_hash, password):  # Upewnij się, że to user.password_hash!
            login_user(user, remember=remember)
            flash('Zalogowano pomyślnie!', 'success')  # Użyj kategorii dla stylizacji Bootstrapem
            next_page = request.args.get('next')  # Pobierz adres, na który użytkownik chciał iść przed zalogowaniem
            return redirect(
                next_page or url_for('main.dashboard'))  # Przekieruj na oryginalny adres lub domyślną stronę

        else:
            flash('Nieprawidłowa nazwa użytkownika/email lub hasło.', 'danger')  # Użyj kategorii dla stylizacji
            # Pozostawiamy render_template, aby formularz z błędami pozostał widoczny
            # return redirect(url_for('bp.login')) # TEJ LINII NIE POTRZEBUJESZ PRZY WTFORMS

    # Renderujemy szablon, przekazując obiekt formularza
    return render_template('auth/login.html', form=form)  # <--- PRZEKAZANIE FORMULARZA


# -- Rejestracja --
@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()  # <--- INICJALIZACJA FORMULARZA WTFORMS

    if form.validate_on_submit():  # <--- Użycie walidacji WTForms
        username = form.username.data
        email = form.email.data
        password = form.password.data

        # Walidatory w forms.py (validate_username, validate_email) zajmują się sprawdzaniem unikalności
        # Możesz usunąć te ręczne sprawdzenia, chyba że chcesz dodatkową logikę.
        # if User.query.filter_by(username=username).first():
        #     flash('Użytkownik już istnieje')
        #     return redirect(url_for('bp.register'))
        # if User.query.filter_by(email=email).first():
        #     flash('Użytkownik już istnieje')
        #     return redirect(url_for('bp.register'))

        hashed_password = generate_password_hash(password)
        # Upewnij się, że w User modelu pole hasła nazywa się password_hash, nie password_hashed
        new_user = User(username=username, email=email, password_hash=hashed_password)

        db.session.add(new_user)
        db.session.commit()
        flash('Rejestracja zakończona sukcesem! Możesz się teraz zalogować.', 'success')
        return redirect(url_for('auth.login'))  # Zmieniono 'bp.login' na 'auth.login'

    # Renderujemy szablon, przekazując obiekt formularza
    return render_template('auth/register.html', form=form)  # <--- PRZEKAZANIE FORMULARZA


# -- Wylogowanie --
@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Zostałeś wylogowany.', 'info')
    return redirect(url_for('auth.login'))  # Zmieniono 'bp.login' na 'auth.login'