from flask import Blueprint, request, jsonify
from ..services.notifications_services import send_email

bp = Blueprint('notifications', __name__, url_prefix='/notify')

@bp.route('/welcome', methods=['POST'])
def notify_welcome():
    """
    Ожидает JSON: { "email": "...", "user_name": "..." }
    """
    data = request.get_json()
    to = [data['email']]
    ctx = {'user_name': data.get('user_name', 'пользователь')}

    send_email(
        to=to,
        subject="Добро пожаловать!",
        template_plain="email/welcome.txt",
        template_html="email/welcome.html",
        **ctx
    )
    return jsonify(status='sent'), 200
