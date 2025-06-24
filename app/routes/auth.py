import bcrypt  # Możesz usunąć, jeśli używasz werkzeug.security
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_mail import Message
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from app import mail, db
from app.models import User
from app.forms import LoginForm, RegistrationForm, PasswordResetRequestForm, PasswordResetForm
from app.services.token_utils import generate_confirmation_token, confirm_token

# Przywrócenie poprzedniej konwencji: nazwa blueprintu jako bp
bp = Blueprint(
    'auth', __name__, url_prefix='/auth', template_folder='templates/auth'
)

@bp.route('/')
def auth_index():
    return redirect(url_for('auth.login'))

# -- Logowanie --
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username_or_email.data
        password = form.password.data
        remember = form.remember_me.data

        user = User.query.filter_by(username=identifier).first() or \
               User.query.filter_by(email=identifier).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            flash('Zalogowano pomyślnie!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Nieprawidłowa nazwa użytkownika/email lub hasło.', 'danger')

    return render_template('auth/login.html', form=form)

# -- Rejestracja --
@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)

        db.session.add(new_user)
        db.session.commit()

        flash('Rejestracja zakończona sukcesem! Możesz się teraz zalogować.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)

# -- Wylogowanie --
@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Zostałeś wylogowany.', 'info')
    return redirect(url_for('auth.login'))

# -- Resetowanie Hasła --
@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = generate_confirmation_token(user.email)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            html = render_template('email/reset_password.html', reset_url=reset_url)

            msg = Message(
                subject='Prośba o reset hasła',
                recipients=[user.email],
                html=html
            )
            try:
                mail.send(msg)
            except Exception as e:
                current_app.logger.error(f'Nie udało się wysłać maila: {e}')
                flash('Wystąpił problem z wysłaniem maila. Spróbuj ponownie później.', 'warning')
                return redirect(url_for('auth.login'))

        flash('Jeśli adres e-mail istnieje, otrzymasz wiadomość z instrukcjami.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_request.html', form=form)

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = confirm_token(token)
    if not email:
        flash('Token jest nieprawidłowy lub wygasł.', 'danger')
        return redirect(url_for('auth.reset_password_request'))

    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first_or_404()
        user.set_password(form.password.data)
        db.session.commit()

        flash('Twoje hasło zostało zaktualizowane.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form)
