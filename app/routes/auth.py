from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_mail import Message
from flask_login import login_user, logout_user, login_required, current_user

from app import mail, db
from app.models import User
from app.forms import LoginForm, RegistrationForm, PasswordResetRequestForm, PasswordResetForm
from app.services.token_utils import generate_confirmation_token, confirm_token
from app.services.notifications_services import wyslij_email


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
        email = form.email.data
        password = form.password.data
        remember = form.remember_me.data

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.email_confirmed:
                flash('Musisz potwierdzić swój e-mail przed zalogowaniem.', 'warning')
                return redirect(url_for('auth.login'))
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
        email = form.email.data

        if User.query.filter_by(email=email).first():
            flash('Ten adres e-mail jest już zajęty. Użyj innego.', 'danger')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=form.username.data,
            email=email
        )
        new_user.set_password(form.password.data)

        db.session.add(new_user)
        db.session.commit()

        token = generate_confirmation_token(email)
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        temat = "Potwierdź swój adres e-mail"
        tresc = (
            f"Cześć {new_user.username},\n\n"
            f"Aby ukończyć rejestrację, kliknij w link:\n{confirm_url}\n\n"
            "Jeśli to nie Ty, zignoruj tę wiadomość."
        )
        wyslij_email(email, temat, tresc)

        flash('Sprawdź swoją skrzynkę e-mail i potwierdź adres, aby dokończyć rejestrację.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)

# -- Podtwierdzenie poczty --
@bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        email = None

    if not email:
        flash('Link potwierdzający jest nieprawidłowy lub wygasł.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first_or_404()
    if user.email_confirmed:
        flash('E-mail już potwierdzony. Zaloguj się.', 'info')
    else:
        user.confirm()
        flash('Dziękujemy! Twój e-mail został potwierdzony.', 'success')
    return redirect(url_for('auth.login'))

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
