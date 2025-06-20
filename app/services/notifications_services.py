from flask import render_template
from flask_mail import Message
from .. import mail

def send_email(to: list[str], subject: str,
               template_plain: str, template_html: str, **ctx):
    """
    Универсальная функция отправки письма:
      - to: список email-адресов
      - subject: тема
      - template_plain: путь до .txt шаблона
      - template_html: путь до .html шаблона
      - ctx: контекст для рендеринга
    """
    msg = Message(subject, recipients=to)
    msg.body = render_template(template_plain, **ctx)
    msg.html = render_template(template_html, **ctx)

    try:
        mail.send(msg)
    except Exception as e:
        # можно логировать или сохранять в БД для ретрая
        print(f"Ошибка отправки письма: {e}")
        raise
