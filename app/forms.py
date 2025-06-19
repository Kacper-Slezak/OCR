from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from models import User

class RegistrationForm(FlaskForm):
    username = StringField('Nazwa użytkownika:', validators=[DataRequired(), Length(min=2, max=15)])
    email = StringField('Email:', validators=[DataRequired(), Length(min=4)])
    password = PasswordField('Hasło:', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Potwierdź hasło:', validators= [DataRequired(), EqualTo('password')])
    submit = SubmitField('Zarejestruj się')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Nazwa użytkownika jest już zajęta.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email już jest zarejestrowany.')

class LoginForm(FlaskForm):
    username_or_email = StringField('Nazwa użytkownika lub email:', validators=[DataRequired()])
    password = PasswordField('Hasło:', validators=[DataRequired()])
    remember_me = BooleanField('Zapamiętaj mnie')
    submit = SubmitField('Zaloguj się')