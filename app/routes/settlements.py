# app/routes/settlements.py
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db  # Importujemy instancję bazy danych
from app.models import ShoppingList, Settlement, User  # Importujemy potrzebne modele
from app.services.settlements_services import calculate_settlements  # Importujemy funkcję rozliczania

bp = Blueprint('settlements', __name__, url_prefix='/settlements')


@bp.route('/')
@login_required
def settlements_dashboard():
    """
    Dashboard rozliczeń - podsumowanie długów i kredytów dla zalogowanego użytkownika.
    """
    user_id = current_user.id

    # Pobieramy bieżące, nierozliczone transakcje, gdzie użytkownik jest dłużnikiem
    my_debts = Settlement.query.filter_by(debtor_id=user_id, is_settled=False).all()
    # Pobieramy bieżące, nierozliczone transakcje, gdzie użytkownik jest wierzycielem
    my_credits = Settlement.query.filter_by(creditor_id=user_id, is_settled=False).all()

    # Możesz dodać logikę do grupowania długów/kredytów per osoba lub per lista zakupów.
    # Na razie wyświetlimy je bezpośrednio.

    # Pobieramy listy zakupów, w których użytkownik jest uczestnikiem lub twórcą,
    # aby móc wywołać obliczenia lub zobaczyć status rozliczeń
    my_shopping_lists_as_participant = ShoppingList.query \
        .join(ShoppingList.participants) \
        .filter(User.id == user_id) \
        .order_by(ShoppingList.created_at.desc()) \
        .all()

    # Dodaj listy, które stworzył użytkownik, jeśli jeszcze nie są w my_shopping_lists_as_participant
    my_created_shopping_lists = ShoppingList.query.filter_by(created_by=user_id) \
        .order_by(ShoppingList.created_at.desc()) \
        .all()

    # Połącz i usuń duplikaty (jeśli użytkownik jest twórcą i uczestnikiem)
    all_related_lists = {}
    for lst in my_shopping_lists_as_participant + my_created_shopping_lists:
        all_related_lists[lst.id] = lst

    sorted_related_lists = sorted(all_related_lists.values(), key=lambda x: x.created_at, reverse=True)

    return render_template('settlements/dashboard.html',
                           my_debts=my_debts,
                           my_credits=my_credits,
                           related_lists=sorted_related_lists)


@bp.route('/list/<int:list_id>/calculate', methods=['POST'])  # Używamy POST dla zmiany stanu
@login_required
def calculate_list_settlements(list_id):
    """
    Wywołuje algorytm rozliczania dla konkretnej listy zakupów.
    Zapewnia, że tylko twórca lub uczestnik listy może wywołać obliczenia.
    """
    shopping_list = ShoppingList.query.get(list_id)
    if not shopping_list:
        flash('Lista zakupów nie została znaleziona.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    # Sprawdź uprawnienia: użytkownik musi być twórcą lub uczestnikiem listy
    is_creator = (shopping_list.created_by == current_user.id)
    is_participant = current_user in shopping_list.participants.all()

    if not (is_creator or is_participant):
        flash('Nie masz uprawnień do obliczania rozliczeń dla tej listy.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    # Wyczyść istniejące nierozliczone transakcje dla tej listy (opcjonalnie, aby przeliczyć od nowa)
    # Możesz to dostosować, jeśli chcesz zachować historię
    Settlement.query.filter_by(shopping_list_id=list_id, is_settled=False).delete()
    db.session.commit()  # Zatwierdź usunięcie przed generowaniem nowych

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
    Tylko dłużnik lub wierzyciel może oznaczyć transakcję.
    """
    settlement = Settlement.query.get(settlement_id)
    if not settlement:
        flash('Rozliczenie nie zostało znalezione.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    # Sprawdź, czy zalogowany użytkownik jest dłużnikiem lub wierzycielem w tej transakcji
    if not (settlement.debtor_id == current_user.id or settlement.creditor_id == current_user.id):
        flash('Nie masz uprawnień do oznaczenia tego rozliczenia.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    if settlement.is_settled:
        flash('To rozliczenie jest już oznaczone jako opłacone.', 'info')
    else:
        settlement.is_settled = True
        settlement.settled_at = datetime.now()  # Ustaw datę uregulowania
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

    # Pobieramy wszystkie rozliczenia, w których użytkownik był dłużnikiem lub wierzycielem
    all_settlements = Settlement.query.filter(
        (Settlement.debtor_id == user_id) | (Settlement.creditor_id == user_id)
    ).order_by(Settlement.created_at.desc()).all()

    return render_template('settlements/history.html', all_settlements=all_settlements)

