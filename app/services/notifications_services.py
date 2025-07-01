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
    za wygasłe czeki — jedno mail na użytkownika z listą wszystkich długów.
    """
    delay_days = int(os.getenv('DEBT_REMINDER_DELAY_DAYS', 3))
    cutoff = datetime.utcnow() - timedelta(days=delay_days)

    rows = (
        db.session.query(Settlement, Receipt, User)
        .join(Receipt, Settlement.receipt_id == Receipt.id)
        .join(User, Settlement.debtor_user_id == User.id)
        .filter(
            Settlement.is_settled == False,
            Receipt.upload_date < cutoff
        )
        .all()
    )

    debts_by_user = {}
    for settlement, receipt, user in rows:
        debts_by_user.setdefault(user.id, {
            'user': user,
            'items': [],
            'total': 0
        })
        entry = debts_by_user[user.id]
        entry['items'].append({
            'receipt_id':    receipt.id,
            'upload_date':   receipt.upload_date.strftime('%Y-%m-%d'),
            'amount':        f"{settlement.amount:.2f}"
        })
        entry['total'] += float(settlement.amount)

    tresc_tpl = Template("""
Cześć {{ user.username }},

Przypominamy, że masz nieuregulowane długi:

{% for d in items -%}
- Paragon nr {{ d.receipt_id }} z dnia {{ d.upload_date }}: {{ d.amount }} PLN
{% endfor %}

Razem do zapłaty: {{ total | round(2) }} PLN

Prosimy o jak najszybszą wpłatę.

Pozdrawiamy,
Zespół OCR
""".lstrip())

    temat_tpl = Template("Przypomnienie o nieuregulowanych długach — {{ total|round(2) }} PLN")

    for data in debts_by_user.values():
        user = data['user']
        temat = temat_tpl.render(total=data['total'])
        tresc = tresc_tpl.render(
            user=user,
            items=data['items'],
            total=data['total']
        )
        wyslij_email(user.email, temat, tresc)
