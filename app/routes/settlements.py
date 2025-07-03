from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, make_response
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList, Settlement, User, Friend, Product
from app.services.settlements_services import calculate_settlements, check_and_update_list_settlement_status
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from io import StringIO
import csv


from sqlalchemy import func, or_

bp = Blueprint('settlements', __name__, url_prefix='/settlements')


@bp.route('/')
@login_required
def settlements_dashboard():
    """
    Dashboard rozliczeń z wykresami i podsumowaniem.
    Ta trasa renderuje szablon HTML z canvasami dla wykresów.
    Dane do wykresów i szczegółów rozliczeń są pobierane asynchronicznie przez JavaScript z API endpointów.
    """
    return render_template('settlements/dashboard_with_charts.html')


@bp.route('/api/stats')
@login_required
def get_settlement_stats():
    """
    API endpoint zwracający statystyki rozliczeń dla zalogowanego użytkownika.
    Dostarcza dane dla przeglądu bilansu netto i wydatków na listy.
    """
    user_id = current_user.id

    total_balance = Decimal('0.00')
    unsettled_transactions_data = []
    spending_per_list = {}

    try:
        # 1. Obliczanie total_balance
        # Pobieramy wszystkie nierozliczone rozliczenia związane z użytkownikiem
        unsettled_settlements = db.session.query(Settlement).filter(
            or_(
                Settlement.debtor_user_id == user_id,
                Settlement.creditor_user_id == user_id,
                Settlement.debtor_friend_id.in_(db.session.query(Friend.id).filter(Friend.user_id == user_id)),
                Settlement.creditor_friend_id.in_(db.session.query(Friend.id).filter(Friend.user_id == user_id))
            ),
            Settlement.is_settled == False
        ).all()

        # Obliczamy saldo na podstawie pobranych rozliczeń
        for settlement in unsettled_settlements:
            # Sprawdzamy czy użytkownik jest wierzycielem (dostaje pieniądze)
            is_user_creditor = (settlement.creditor_user_id == user_id) or \
                               (settlement.creditor_friend_id and settlement.creditor_friend.user_id == user_id)

            # Sprawdzamy czy użytkownik jest dłużnikiem (płaci)
            is_user_debtor = (settlement.debtor_user_id == user_id) or \
                             (settlement.debtor_friend_id and settlement.debtor_friend.user_id == user_id)

            if is_user_creditor:
                total_balance += settlement.amount
            elif is_user_debtor:
                total_balance -= settlement.amount

        # 2. Szczegółowe nierozliczone transakcje
        for s in unsettled_settlements:
            debtor_name = "N/A"
            if s.debtor_user:
                debtor_name = s.debtor_user.username
            elif s.debtor_friend:
                debtor_name = s.debtor_friend.name

            creditor_name = "N/A"
            if s.creditor_user:
                creditor_name = s.creditor_user.username
            elif s.creditor_friend:
                creditor_name = s.creditor_friend.name

            # Określamy typ transakcji z perspektywy zalogowanego użytkownika
            transaction_type = ''
            if (s.creditor_user_id == user_id) or (s.creditor_friend_id and s.creditor_friend.user_id == user_id):
                transaction_type = 'owes_you'
            elif (s.debtor_user_id == user_id) or (s.debtor_friend_id and s.debtor_friend.user_id == user_id):
                transaction_type = 'you_owe'

            unsettled_transactions_data.append({
                'id': s.id,
                'debtor_name': debtor_name,
                'creditor_name': creditor_name,
                'amount': float(s.amount),
                'shopping_list_name': s.shopping_list_ref.name if s.shopping_list_ref else 'N/A',
                'type': transaction_type
            })

        # 3. Wydatki na Listy Zakupów
        # Pobieramy ID wszystkich list, w których użytkownik jest twórcą lub uczestnikiem
        user_related_list_ids = db.session.query(ShoppingList.id).filter(
            or_(
                ShoppingList.created_by == user_id,
                ShoppingList.participants.any(User.id == user_id)
            )
        ).subquery()

        # Sumujemy ceny produktów tylko z tych list
        spending_data = db.session.query(
            ShoppingList.name, func.sum(Product.price)
        ).join(Product, ShoppingList.id == Product.shopping_list_id).filter(
            ShoppingList.id.in_(user_related_list_ids),
            Product.price.isnot(None)  # Sprawdzenie, żeby uniknąć problemów z NULL
        ).group_by(ShoppingList.name).all()

        for list_name, total_spent in spending_data:
            spending_per_list[list_name] = float(total_spent or 0.0)

        print(f"DEBUG: User {user_id} - Found {len(unsettled_settlements)} unsettled settlements")
        print(f"DEBUG: Total balance calculated: {total_balance}")

    except Exception as e:
        print(f"Błąd podczas pobierania statystyk rozliczeń: {e}")
        return jsonify({'error': 'Nie udało się pobrać statystyk rozliczeń'}), 500

    return jsonify({
        'total_balance': float(total_balance),
        'unsettled_transactions': unsettled_transactions_data,
        'spending_per_list': spending_per_list
    })


@bp.route('/api/activity')
@login_required
def get_settlement_activity():
    """
    API endpoint zwracający dane o aktywności rozliczeń (liczba rozliczeń na miesiąc).
    Uwzględnia rozliczenia, w których użytkownik jest bezpośrednio stroną lub jego znajomy.
    """
    user_id = current_user.id
    monthly_activity = []

    try:
        # Złożone zapytanie, aby uwzględnić rozliczenia, gdzie użytkownik jest bezpośrednio stroną
        # LUB gdzie znajomy użytkownika jest stroną
        activity_data = db.session.query(
            func.strftime('%Y-%m', Settlement.created_at),
            func.count(Settlement.id)
        ).filter(
            or_(
                (Settlement.creditor_user_id == user_id),
                (Settlement.debtor_user_id == user_id),
                (Settlement.creditor_friend_id.in_(
                    db.session.query(Friend.id).filter(Friend.user_id == user_id)
                )),
                (Settlement.debtor_friend_id.in_(
                    db.session.query(Friend.id).filter(Friend.user_id == user_id)
                ))
            )
        ).group_by(
            func.strftime('%Y-%m', Settlement.created_at)
        ).order_by(
            func.strftime('%Y-%m', Settlement.created_at)
        ).all()

        monthly_activity = [
            {'month': row[0], 'settlements': row[1]}
            for row in activity_data
        ]
    except Exception as e:
        print(f"Błąd podczas pobierania aktywności rozliczeń: {e}")
        return jsonify({'error': 'Nie udało się pobrać aktywności rozliczeń'}, 500)

    return jsonify({'monthly_activity': monthly_activity})


@bp.route('/api/settlement-trends')
@login_required
def get_settlement_trends():
    """
    API endpoint zwracający dane o trendach salda w czasie (saldo netto w kolejnych tygodniach).
    Uwzględnia rozliczenia, w których użytkownik jest bezpośrednio stroną lub jego znajomy.
    """
    user_id = current_user.id
    trends_data = []

    try:
        # Pobieramy wszystkie rozliczenia dla danego użytkownika (lub jego znajomych), posortowane chronologicznie
        all_settlements = db.session.query(Settlement).filter(
            or_(
                (Settlement.creditor_user_id == user_id),
                (Settlement.debtor_user_id == user_id),
                (Settlement.creditor_friend_id.in_(
                    db.session.query(Friend.id).filter(Friend.user_id == user_id)
                )),
                (Settlement.debtor_friend_id.in_(
                    db.session.query(Friend.id).filter(Friend.user_id == user_id)
                ))
            )
        ).order_by(Settlement.created_at).all()

        current_balance = Decimal('0.00')
        weekly_balances = defaultdict(Decimal)

        for settlement in all_settlements:
            # Określamy, czy rozliczenie wpływa na saldo zalogowanego użytkownika
            # Użytkownik jest wierzycielem LUB znajomy użytkownika jest wierzycielem
            is_user_or_friend_creditor = (settlement.creditor_user_id == user_id) or \
                                         (
                                                     settlement.creditor_friend_id and settlement.creditor_friend.user_id == user_id)

            # Użytkownik jest dłużnikiem LUB znajomy użytkownika jest dłużnikiem
            is_user_or_friend_debtor = (settlement.debtor_user_id == user_id) or \
                                       (settlement.debtor_friend_id and settlement.debtor_friend.user_id == user_id)

            if is_user_or_friend_creditor:
                current_balance += settlement.amount
            elif is_user_or_friend_debtor:
                current_balance -= settlement.amount

            year, week_num, _ = settlement.created_at.isocalendar()
            week_key = f"{year}-{week_num:02d}"

            weekly_balances[week_key] = current_balance

        end_date = datetime.now()
        for i in range(12):  # Ostatnie 12 tygodni
            week_date = end_date - timedelta(weeks=i)
            year, week_num, _ = week_date.isocalendar()
            week_key = f"{year}-{week_num:02d}"

            start_of_week = week_date - timedelta(days=week_date.weekday())
            week_label = start_of_week.strftime('%Y-%m-%d')

            balance_for_week = weekly_balances.get(week_key, Decimal('0.00'))

            trends_data.insert(0, {
                'week': week_label,
                'total_amount': float(balance_for_week)
            })

    except Exception as e:
        print(f"Błąd podczas pobierania trendów rozliczeń: {e}")
        return jsonify({'error': 'Nie udało się pobrać trendów rozliczeń'}, 500)

    return jsonify({'trends': trends_data})


@bp.route('/list/<int:list_id>/calculate', methods=['POST'])
@login_required
def calculate_list_settlements(list_id):
    """
    Oblicza rozliczenia dla pojedynczej listy zakupów.
    (Ta trasa jest używana wewnętrznie lub w specyficznych przypadkach,
    główny przycisk do obliczeń jest teraz na dashboardzie głównym).
    """
    shopping_list = ShoppingList.query.get(list_id)
    if not shopping_list:
        flash('Lista zakupów nie została znaleziona.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    is_creator = (shopping_list.created_by == current_user.id)
    is_participant = current_user in shopping_list.participants.all()

    if not (is_creator or is_participant):
        flash('Nie masz uprawnień do obliczania rozliczeń dla tej listy.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    # Czyścimy istniejące rozliczenia dla tej listy przed ponownym przeliczeniem
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

    # Sprawdzamy, czy zalogowany użytkownik jest stroną w tej transakcji
    is_user_debtor = (settlement.debtor_user_id == current_user.id)
    is_user_creditor = (settlement.creditor_user_id == current_user.id)

    # Sprawdzamy, czy zalogowany użytkownik jest właścicielem znajomego będącego stroną
    is_friend_debtor_owned = (settlement.debtor_friend_id and settlement.debtor_friend.user_id == current_user.id)
    is_friend_creditor_owned = (settlement.creditor_friend_id and settlement.creditor_friend.user_id == current_user.id)

    if not (is_user_debtor or is_user_creditor or is_friend_debtor_owned or is_friend_creditor_owned):
        flash('Nie masz uprawnień do oznaczenia tego rozliczenia.', 'error')
        return redirect(url_for('settlements.settlements_dashboard'))

    if settlement.is_settled:
        flash('To rozliczenie jest już oznaczone jako opłacone.', 'info')
    else:
        settlement.is_settled = True
        settlement.settled_at = datetime.now()
        db.session.commit()
        flash('Rozliczenie zostało pomyślnie oznaczone jako opłacone.', 'success')

        # Po uregulowaniu pojedynczego rozliczenia, sprawdzamy status całej listy
        check_and_update_list_settlement_status(settlement.shopping_list_id)

    return redirect(url_for('settlements.settlements_dashboard'))


@bp.route('/history')
@login_required
def settlement_history():
    """
    Wyświetla historię wszystkich rozliczeń użytkownika (opłaconych i nieopłaconych).
    Uwzględnia rozliczenia, w których użytkownik jest bezpośrednio stroną lub jego znajomy.
    """
    user_id = current_user.id

    # Pobieramy wszystkie rozliczenia, w których użytkownik był dłużnikiem LUB wierzycielem
    # LUB gdzie znajomy użytkownika był dłużnikiem LUB wierzycielem
    all_settlements = db.session.query(Settlement).filter(
        or_(
            (Settlement.debtor_user_id == user_id),
            (Settlement.creditor_user_id == user_id),
            (Settlement.debtor_friend_id.in_(
                db.session.query(Friend.id).filter(Friend.user_id == user_id)
            )),
            (Settlement.creditor_friend_id.in_(
                db.session.query(Friend.id).filter(Friend.user_id == user_id)
            ))
        )
    ).order_by(Settlement.created_at.desc()).all()

    return render_template('settlements/history.html', all_settlements=all_settlements)

@bp.route('/transakcje.csv')
def eksportuj_transakcje_csv():
    """
    Generuje plik CSV ze wszystkimi rekordami Settlement
    """

    naglowki = ['ID', 'ID listy', 'ID dluznika', 'ID wierzyciela',
                'Kwota', 'Utworzono', 'Rozliczono']


    bufor = StringIO()
    writer = csv.writer(bufor, delimiter=';')
    writer.writerow(naglowki)

    # Pobieramy wszystkie transakcje
    transakcje = Settlement.query.all()
    for t in transakcje:
        if t.settled_at:
            rozliczono = t.settled_at.strftime('%Y-%m-%d %H:%M:%S')
        else:
            rozliczono = 'nie'
        writer.writerow([
            t.id,
            t.shopping_list_id,
            t.debtor_friend_id,
            t.creditor_friend_id,
            f"{t.amount:.2f}",
            t.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            rozliczono,
        ])

    # Tworzymy odpowiedź
    output = make_response(bufor.getvalue())
    output.headers['Content-Type'] = 'text/csv; charset=utf-8'
    output.headers['Content-Disposition'] = 'attachment; filename=transakcje.csv'
    return output

