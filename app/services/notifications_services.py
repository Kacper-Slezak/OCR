import os
from datetime import datetime, timedelta

from flask import current_app
from flask_mail import Message
from jinja2 import Template
from email_validator import validate_email, EmailNotValidError

from app import db, mail
from app.models import User, Settlement

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def wyslij_email(adres: str, temat: str, tresc: str) -> None:
    """
    Wysyła pojedynczy e-mail przez Flask-Mail.
    """
    try:
        validate_email(adres)
    except EmailNotValidError:
        current_app.logger.warning(f"Nieprawidłowy e-mail: {adres}")
        return

    msg = Message(
        subject=temat,
        sender=current_app.config['MAIL_USERNAME'],
        recipients=[adres],
        body=tresc
    )
    mail.send(msg)


def wyslij_powiadomienia(temat_tpl: str, tresc_tpl: str, kontekst_fn) -> None:
    """
    Masowa wysyłka powiadomień do wszystkich użytkowników.
    """
    uzytkownicy = User.query.all()
    for u in uzytkownicy:
        ctx = kontekst_fn(u)
        temat = Template(temat_tpl).render(**ctx)
        tresc = Template(tresc_tpl).render(**ctx)
        wyslij_email(u.email, temat, tresc)

def wyslij_przypomnienia_dluznikom() -> None:
    rows = Settlement.query.filter_by(is_settled=False).all()
 
    for s in rows:
        if s.debtor_user_id:
            email    = s.debtor_user.email
            username = s.debtor_user.username
        else:
            email    = s.debtor_friend.email
            username = s.debtor_friend.name

        wyslij_email(
            email,
            f"Przypomnienie o długu: {s.amount:.2f} PLN",
            f"Cześć {username},\n\nMasz do zapłaty {s.amount:.2f} PLN "
            f"z rozliczenia #{s.id} utworzonego {s.created_at:%Y-%m-%d}."
        )
