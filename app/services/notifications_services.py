import os
from datetime import datetime, timedelta

from flask import current_app
from flask_mail import Message
from jinja2 import Template
from email_validator import validate_email, EmailNotValidError

from app import db, mail
from app.models import User, Receipt, Settlement

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
    """
    Codzienna funkcja APScheduler, wysyła przypomnienia dłużnikom
    za wygasłe czeki.
    """
    delay_days = int(os.getenv('DEBT_REMINDER_DELAY_DAYS', 3))
    cutoff = datetime.utcnow() - timedelta(days=delay_days)

    debts = (
        db.session.query(Settlement, Receipt, User)
        .join(Receipt, Settlement.receipt_id == Receipt.id)
        .join(User, Settlement.debtor_id == User.id)
        .filter(
            Settlement.is_settled == False,
            Receipt.upload_date < cutoff
        )
        .all()
    )

    temat_tpl = "Przypomnienie: nieuregulowany dług za paragon {{ receipt.id }}"
    tresc_tpl = (
        "Cześć {{ user.username }},\n\n"
        "Przypominamy, że paragon nr {{ receipt.id }} z dnia {{ receipt.upload_date }} "
        "ciągle nie został uregulowany kwotą {{ settlement.amount }}.\n\n"
        "Prosimy o jak najszybszą wpłatę.\n\n"
        "Pozdrawiamy,\nZespół OCR"
    )

    for settlement, receipt, user in debts:
        kontekst = {'user': user, 'receipt': receipt, 'settlement': settlement}
        temat = Template(temat_tpl).render(**kontekst)
        tresc = Template(tresc_tpl).render(**kontekst)
        wyslij_email(user.email, temat, tresc)
