from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError

# Poprawka: Poprawny import User z pakietu app
from app.models import User

class RegistrationForm(FlaskForm):
    username = StringField('Nazwa użytkownika:', validators=[DataRequired(), Length(min=2, max=15)])
    email = StringField('Email:', validators=[DataRequired(), Email(), Length(min=4)]) # Dodano Email() validator
    password = PasswordField('Hasło:', validators=[DataRequired(), Length(min=8)])
    # Poprawka: Literówka w EqualTo - 'passwword' -> 'password'
    confirm_password = PasswordField('Potwierdź hasło:', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Zarejestruj się')

    # Metody walidujące MUSZĄ być wewnątrz klasy formularza
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ta nazwa użytkownika jest już zajęta. Wybierz inną.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Ten adres email jest już zarejestrowany. Proszę użyć innego.')


class LoginForm(FlaskForm):
    username_or_email = StringField('Nazwa użytkownika lub email:', validators=[DataRequired()])
    password = PasswordField('Hasło:', validators=[DataRequired()])
    remember_me = BooleanField('Zapamiętaj mnie')
    submit = SubmitField('Zaloguj się')