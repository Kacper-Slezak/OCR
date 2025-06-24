from flask import Blueprint, request, jsonify
from app.models import User
from app.services.notifications_services import wyslij_powiadomienia

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/send-all', methods=['POST'])
def send_all():
    """
    POST /notifications/send-all
    {
      "temat": "Witaj {{ user.name }}!",
      "tresc": "Masz teraz {{ user.notifications_count }} powiadomień."
    }
    """
    data = request.get_json(force=True)
    temat = data.get('temat')
    tresc = data.get('tresc')
    if not temat or not tresc:
        return jsonify({'error': "Brakuje pola 'temat' lub 'tresc'"}), 400

    wyslij_powiadomienia(
        temat_tpl=temat,
        tresc_tpl=tresc,
        kontekst_fn=lambda u: {'user': u}
    )
    count = User.query.count()
    return jsonify({'status': 'wysłano', 'count': count}), 202
