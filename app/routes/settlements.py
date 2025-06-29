# app/routes/settlements.py
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList, Settlement, User, Friend
from app.services.settlements_services import calculate_settlements
from datetime import datetime

bp = Blueprint('settlements', __name__, url_prefix='/settlements')


@bp.route('/')
@login_required
def settlements_dashboard():
    """
    Dashboard rozliczeń - podsumowanie długów i kredytów dla zalogowanego użytkownika.
    Uwzględnia rozliczenia z innymi użytkownikami i ze znajomymi.
    """
    user_id = current_user.id

    # Rozliczenia, gdzie zalogowany użytkownik jest dłużnikiem (innemu Userowi lub Friendowi)
    my_debts = Settlement.query.filter_by(debtor_user_id=user_id, is_settled=False).all()
    # Rozliczenia, gdzie zalogowany użytkownik jest wierzycielem (od innego Usera lub Frienda)
    my_credits = Settlement.query.filter_by(creditor_user_id=user_id, is_settled=False).all()

    # Możemy również chcieć wyświetlić rozliczenia, gdzie Friend użytkownika jest dłużnikiem/wierzycielem
    # (to jest zaawansowane i wymagałoby zdefiniowania, kto jest "odpowiedzialny" za długi znajomych)
    # Na razie skupmy się na rozliczeniach, gdzie JEDEN ZAREJESTROWANY USER JEST JEDNĄ ZE STRON.

    # Agregacja do pokazania globalnego salda per osoba/znajomy, aby dashboard był czytelniejszy
    from collections import defaultdict
    global_balances = defaultdict(Decimal)  # Klucze: (typ, id), Wartości: kwota netto

    # Agreguj, gdy current_user jest dłużnikiem
    for debt in my_debts:
        if debt.creditor_user_id:
            global_balances[('user', debt.creditor_user_id)] -= debt.amount
        elif debt.creditor_friend_id:
            global_balances[('friend', debt.creditor_friend_id)] -= debt.amount

    # Agreguj, gdy current_user jest wierzycielem
    for credit in my_credits:
        if credit.debtor_user_id:
            global_balances[('user', credit.debtor_user_id)] += credit.amount
        elif credit.debtor_friend_id:
            global_balances[('friend', credit.debtor_friend_id)] += credit.amount

    # Przygotowanie do wyświetlenia
    net_balances_to_show = []
    for (entity_type, entity_id), net_amount in global_balances.items():
        if net_amount != Decimal('0.00'):
            entity_name = "Nieznane"
            if entity_type == 'user':
                entity = User.query.get(entity_id)
                entity_name = entity.username if entity else "Nieznany Użytkownik"
            elif entity_type == 'friend':
                entity = Friend.query.get(entity_id)
                entity_name = entity.name if entity else "Nieznany Znajomy"

            net_balances_to_show.append({
                'entity_type': entity_type,
                'entity_id': entity_id,
                'entity_name': entity_name,
                'amount': net_amount,
                'type': 'owes_you' if net_amount > 0 else 'you_owe'
            })

    # Pobieramy listy zakupów, w których użytkownik jest uczestnikiem lub twórcą,
    # aby móc wywołać obliczenia lub zobaczyć status rozliczeń
    my_shopping_lists_as_participant = ShoppingList.query \
        .join(ShoppingList.participants) \
        .filter(User.id == user_id) \
        .order_by(ShoppingList.created_at.desc()) \
        .all()

    my_created_shopping_lists = ShoppingList.query.filter_by(created_by=user_id) \
        .order_by(ShoppingList.created_at.desc()) \
        .all()

    all_related_lists = {}
    for lst in my_shopping_lists_as_participant + my_created_shopping_lists:
        all_related_lists[lst.id] = lst

    sorted_related_lists = sorted(all_related_lists.values(), key=lambda x: x.created_at, reverse=True)

    return render_template('settlements/dashboard.html',
                           my_debts=my_debts,
                           my_credits=my_credits,
                           related_lists=sorted_related_lists,
                           net_balances=net_balances_to_show)  # Przekazujemy zagregowane salda


@bp.route('/list/<int:list_id>/calculate', methods=['POST'])
@login_required
def calculate_list_settlements(list_id):
    shopping_list = ShoppingList.query.get(list_id)
    if not shopping_list:
        flash('Lista zakupów nie została znaleziona.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    is_creator = (shopping_list.created_by == current_user.id)
    is_participant = current_user in shopping_list.participants.all()

    if not (is_creator or is_participant):
        flash('Nie masz uprawnień do obliczania rozliczeń dla tej listy.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    # Wyczyść istniejące nierozliczone transakcje dla tej listy
    # (Pamiętaj, że to usunie wszystkie Settlementy dla tej listy, niezależnie od statusu,
    # jeśli chcesz zachować historię, zmień to na filtrowanie po is_settled=False)
    Settlement.query.filter_by(shopping_list_id=list_id).delete()
    db.session.commit()

    new_settlements = calculate_settlements(list_id)
    if new_settlements:
        flash(f'Rozliczenia dla listy "{shopping_list.name}" zostały pomyślnie obliczone i zapisane.', 'success')
    else:
        flash(f'Nie udało się wygenerować rozliczeń dla listy "{shopping_list.name}" lub brak danych do rozliczenia.',
              'info')

    return redirect(url_for('settlements.settlements_dashboard'))


@bp.route('/settle/<int:settlement_id>', methods=['POST'])
@login_required
def settle_single_transaction(settlement_id):
    """
    Oznacza pojedyncze rozliczenie jako opłacone.
    Tylko zalogowany użytkownik, który jest dłużnikiem LUB wierzycielem w tej transakcji, może ją oznaczyć.
    """
    settlement = Settlement.query.get_or_404(settlement_id)

    # Sprawdź, czy zalogowany użytkownik jest stroną w tej transakcji
    is_user_debtor = (settlement.debtor_user_id == current_user.id)
    is_user_creditor = (settlement.creditor_user_id == current_user.id)

    if not (is_user_debtor or is_user_creditor):
        flash('Nie masz uprawnień do oznaczenia tego rozliczenia.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    if settlement.is_settled:
        flash('To rozliczenie jest już oznaczone jako opłacone.', 'info')
    else:
        settlement.is_settled = True
        settlement.settled_at = datetime.now()
        db.session.commit()
        flash('Rozliczenie zostało pomyślnie oznaczone jako opłacone.', 'success')

    return redirect(url_for('settlements.settlements_dashboard'))


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
