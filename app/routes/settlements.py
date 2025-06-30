# app/routes/settlements.py
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList, Settlement, User, Friend
from app.services.settlements_services import calculate_settlements
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func, extract

bp = Blueprint('settlements', __name__, url_prefix='/settlements')


@bp.route('/')
@login_required
def settlements_dashboard():
    """
    Nowy dashboard rozliczeń z wykresami - skupiony na wizualizacji danych
    """
    return render_template('settlements/dashboard_with_charts.html')


@bp.route('/api/stats')
@login_required
def get_settlement_stats():
    """
    API endpoint zwracający statystyki rozliczeń dla zalogowanego użytkownika
    """
    user_id = current_user.id

    # Pobierz wszystkie nierozliczone transakcje
    my_debts = Settlement.query.filter_by(debtor_user_id=user_id, is_settled=False).all()
    my_credits = Settlement.query.filter_by(creditor_user_id=user_id, is_settled=False).all()

    # Agregacja sald
    global_balances = defaultdict(Decimal)

    # Agreguj długi (current_user jest dłużnikiem)
    for debt in my_debts:
        if debt.creditor_user_id:
            global_balances[('user', debt.creditor_user_id)] -= debt.amount
        elif debt.creditor_friend_id:
            global_balances[('friend', debt.creditor_friend_id)] -= debt.amount

    # Agreguj kredyty (current_user jest wierzycielem)
    for credit in my_credits:
        if credit.debtor_user_id:
            global_balances[('user', credit.debtor_user_id)] += credit.amount
        elif credit.debtor_friend_id:
            global_balances[('friend', credit.debtor_friend_id)] += credit.amount

    # Przygotuj dane do wysłania
    balances_list = []
    total_credits = Decimal('0.00')
    total_debts = Decimal('0.00')

    for (entity_type, entity_id), net_amount in global_balances.items():
        if net_amount != Decimal('0.00'):
            entity_name = "Nieznane"
            if entity_type == 'user':
                entity = User.query.get(entity_id)
                entity_name = entity.username if entity else "Nieznany Użytkownik"
            elif entity_type == 'friend':
                entity = Friend.query.get(entity_id)
                entity_name = entity.name if entity else "Nieznany Znajomy"

            balance_type = 'owes_you' if net_amount > 0 else 'you_owe'

            balances_list.append({
                'entity_type': entity_type,
                'entity_id': entity_id,
                'entity_name': entity_name,
                'amount': float(net_amount),
                'type': balance_type
            })

            # Dodaj do sum
            if net_amount > 0:
                total_credits += net_amount
            else:
                total_debts += abs(net_amount)

    return jsonify({
        'balances': balances_list,
        'total_credits': float(total_credits),
        'total_debts': float(total_debts),
        'total_balance': float(total_credits - total_debts)
    })


@bp.route('/api/activity')
@login_required
def get_settlement_activity():
    """
    API endpoint zwracający aktywność rozliczeń w ostatnich 6 miesiącach
    """
    user_id = current_user.id

    # Pobierz rozliczenia z ostatnich 6 miesięcy
    six_months_ago = datetime.now() - timedelta(days=180)

    settlements = Settlement.query.filter(
        ((Settlement.debtor_user_id == user_id) | (Settlement.creditor_user_id == user_id)),
        Settlement.created_at >= six_months_ago
    ).all()

    # Grupuj po miesiącach
    monthly_data = defaultdict(lambda: {'count': 0, 'amount': Decimal('0.00')})

    for settlement in settlements:
        month_key = settlement.created_at.strftime('%Y-%m')
        month_name = settlement.created_at.strftime('%b')

        monthly_data[month_key]['month'] = month_name
        monthly_data[month_key]['count'] += 1
        monthly_data[month_key]['amount'] += settlement.amount

    # Przygotuj dane do wysłania (ostatnie 6 miesięcy)
    activity_list = []
    for i in range(6):
        date = datetime.now() - timedelta(days=30 * i)
        month_key = date.strftime('%Y-%m')
        month_name = date.strftime('%b')

        data = monthly_data.get(month_key, {'month': month_name, 'count': 0, 'amount': Decimal('0.00')})
        activity_list.append({
            'month': month_name,
            'settlements': data['count'],
            'amount': float(data['amount'])
        })

    # Odwróć kolejność, żeby najstarsze były pierwsze
    activity_list.reverse()

    return jsonify({'monthly_activity': activity_list})


@bp.route('/api/recent-lists')
@login_required
def get_recent_shopping_lists():
    """
    API endpoint zwracający ostatnie listy zakupów użytkownika
    """
    user_id = current_user.id

    # Pobierz listy, w których użytkownik uczestniczy lub które stworzył
    my_lists_as_participant = ShoppingList.query \
        .join(ShoppingList.participants) \
        .filter(User.id == user_id) \
        .order_by(ShoppingList.created_at.desc()) \
        .limit(5) \
        .all()

    my_created_lists = ShoppingList.query.filter_by(created_by=user_id) \
        .order_by(ShoppingList.created_at.desc()) \
        .limit(5) \
        .all()

    # Połącz i usuń duplikaty
    all_lists = {}
    for lst in my_lists_as_participant + my_created_lists:
        all_lists[lst.id] = {
            'id': lst.id,
            'name': lst.name,
            'created_at': lst.created_at.strftime('%d.%m.%Y'),
            'is_completed': lst.is_completed,
            'is_fully_settled': lst.is_fully_settled,
            'can_calculate': not lst.is_fully_settled
        }

    # Sortuj po dacie i weź tylko 5 najnowszych
    sorted_lists = sorted(all_lists.values(),
                          key=lambda x: datetime.strptime(x['created_at'], '%d.%m.%Y'),
                          reverse=True)[:5]

    return jsonify({'recent_lists': sorted_lists})


@bp.route('/list/<int:list_id>/calculate', methods=['POST'])
@login_required
def calculate_list_settlements(list_id):
    shopping_list = ShoppingList.query.get(list_id)
    if not shopping_list:
        return jsonify({'error': 'Lista zakupów nie została znaleziona.'}), 404

    is_creator = (shopping_list.created_by == current_user.id)
    is_participant = current_user in shopping_list.participants.all()

    if not (is_creator or is_participant):
        return jsonify({'error': 'Nie masz uprawnień do obliczania rozliczeń dla tej listy.'}), 403

    # Wyczyść istniejące nierozliczone transakcje dla tej listy
    Settlement.query.filter_by(shopping_list_id=list_id, is_settled=False).delete()
    db.session.commit()

    new_settlements = calculate_settlements(list_id)

    if new_settlements:
        return jsonify({
            'success': True,
            'message': f'Rozliczenia dla listy "{shopping_list.name}" zostały pomyślnie obliczone.',
            'settlements_count': len(new_settlements)
        })
    else:
        return jsonify({
            'success': False,
            'message': f'Nie udało się wygenerować rozliczeń dla listy "{shopping_list.name}" lub brak danych do rozliczenia.'
        })


@bp.route('/settle/<int:settlement_id>', methods=['POST'])
@login_required
def settle_single_transaction(settlement_id):
    """
    Oznacza pojedyncze rozliczenie jako opłacone.
    """
    settlement = Settlement.query.get_or_404(settlement_id)

    # Sprawdź uprawnienia
    is_user_debtor = (settlement.debtor_user_id == current_user.id)
    is_user_creditor = (settlement.creditor_user_id == current_user.id)

    if not (is_user_debtor or is_user_creditor):
        return jsonify({'error': 'Nie masz uprawnień do oznaczenia tego rozliczenia.'}), 403

    if settlement.is_settled:
        return jsonify({'message': 'To rozliczenie jest już oznaczone jako opłacone.'})
    else:
        settlement.is_settled = True
        settlement.settled_at = datetime.now()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Rozliczenie zostało pomyślnie oznaczone jako opłacone.'})


@bp.route('/settle-with/<entity_type>/<int:entity_id>', methods=['POST'])
@login_required
def settle_all_with_entity(entity_type, entity_id):
    """
    Oznacza wszystkie rozliczenia z daną osobą jako opłacone
    """
    user_id = current_user.id

    if entity_type == 'user':
        # Rozliczenia między current_user a innym userem
        settlements = Settlement.query.filter(
            ((Settlement.debtor_user_id == user_id) & (Settlement.creditor_user_id == entity_id)) |
            ((Settlement.debtor_user_id == entity_id) & (Settlement.creditor_user_id == user_id)),
            Settlement.is_settled == False
        ).all()
    elif entity_type == 'friend':
        # Rozliczenia między current_user a friendem
        settlements = Settlement.query.filter(
            ((Settlement.debtor_user_id == user_id) & (Settlement.creditor_friend_id == entity_id)) |
            ((Settlement.debtor_friend_id == entity_id) & (Settlement.creditor_user_id == user_id)),
            Settlement.is_settled == False
        ).all()
    else:
        return jsonify({'error': 'Nieprawidłowy typ encji.'}), 400

    if not settlements:
        return jsonify({'message': 'Brak rozliczeń do oznaczenia.'})

    # Oznacz wszystkie jako opłacone
    for settlement in settlements:
        settlement.is_settled = True
        settlement.settled_at = datetime.now()

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Oznaczono {len(settlements)} rozliczeń jako opłacone.',
        'settled_count': len(settlements)
    })


@bp.route('/history')
@login_required
def settlement_history():
    """
    Wyświetla historię wszystkich rozliczeń użytkownika (opłaconych i nieopłaconych).
    """
    user_id = current_user.id

    # Pobieramy wszystkie rozliczenia, w których użytkownik był dłużnikiem LUB wierzycielem
    all_settlements = Settlement.query.filter(
        (Settlement.debtor_user_id == user_id) | (Settlement.creditor_user_id == user_id)
    ).order_by(Settlement.created_at.desc()).all()

    return render_template('settlements/history.html', all_settlements=all_settlements)


@bp.route('/api/settlement-trends')
@login_required
def get_settlement_trends():
    """
    API endpoint zwracający trendy rozliczeń w czasie
    """
    user_id = current_user.id

    # Pobierz rozliczenia z ostatniego roku
    one_year_ago = datetime.now() - timedelta(days=365)

    settlements = Settlement.query.filter(
        ((Settlement.debtor_user_id == user_id) | (Settlement.creditor_user_id == user_id)),
        Settlement.created_at >= one_year_ago
    ).all()

    # Grupuj po tygodniach
    weekly_data = defaultdict(lambda: {
        'week': '',
        'total_amount': Decimal('0.00'),
        'credits': Decimal('0.00'),
        'debts': Decimal('0.00'),
        'count': 0
    })

    for settlement in settlements:
        # Oblicz numer tygodnia
        week_start = settlement.created_at - timedelta(days=settlement.created_at.weekday())
        week_key = week_start.strftime('%Y-%W')
        week_display = week_start.strftime('%d.%m')

        weekly_data[week_key]['week'] = week_display
        weekly_data[week_key]['count'] += 1
        weekly_data[week_key]['total_amount'] += settlement.amount

        # Sprawdź czy user jest wierzycielem czy dłużnikiem
        if settlement.creditor_user_id == user_id:
            weekly_data[week_key]['credits'] += settlement.amount
        elif settlement.debtor_user_id == user_id:
            weekly_data[week_key]['debts'] += settlement.amount

    # Przygotuj dane z ostatnich 12 tygodni
    trends_list = []
    for i in range(12):
        week_date = datetime.now() - timedelta(weeks=i)
        week_start = week_date - timedelta(days=week_date.weekday())
        week_key = week_start.strftime('%Y-%W')
        week_display = week_start.strftime('%d.%m')

        data = weekly_data.get(week_key, {
            'week': week_display,
            'total_amount': Decimal('0.00'),
            'credits': Decimal('0.00'),
            'debts': Decimal('0.00'),
            'count': 0
        })

        trends_list.append({
            'week': data['week'],
            'total_amount': float(data['total_amount']),
            'credits': float(data['credits']),
            'debts': float(data['debts']),
            'count': data['count']
        })

    trends_list.reverse()  # Najstarsze pierwsze

    return jsonify({'trends': trends_list})