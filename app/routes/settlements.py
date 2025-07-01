# app/routes/settlements.py
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db  # Zakładam, że 'db' to instancja SQLAlchemy
from app.models import ShoppingList, Settlement, User, Friend, Product  # Upewnij się, że User i Friend są zaimportowane
from app.services.settlements_services import calculate_settlements, _check_and_update_list_settlement_status
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func, extract  # func do agregacji, extract do wyciągania części daty

bp = Blueprint('settlements', __name__, url_prefix='/settlements')


@bp.route('/')
@login_required
def settlements_dashboard():
    """
    Dashboard rozliczeń z wykresami - skupiony na wizualizacji danych.
    Ta trasa renderuje szablon HTML z canvasami dla wykresów.
    Dane do wykresów i ostatnich list są pobierane asynchronicznie przez JavaScript z API endpointów.
    """
    # Ścieżka do szablonu powinna być poprawna. Jeśli Twój settlements_dashboard.html jest w
    # templates/settlements/dashboard_with_charts.html, to ta linia jest OK.
    return render_template('settlements/dashboard_with_charts.html')


@bp.route('/api/stats')
@login_required
def get_settlement_stats():
    """
    API endpoint zwracający statystyki rozliczeń dla zalogowanego użytkownika.
    Dostarcza dane dla przeglądu bilansu netto i wydatków na listy.
    """
    user_id = current_user.id  # Pobierz ID zalogowanego użytkownika

    total_balance = Decimal('0.00')
    balances = []
    spending_per_list = {}

    try:
        # 1. Obliczanie total_balance (całkowite saldo netto dla zalogowanego użytkownika)
        # Suma należności (inni są winni Tobie) - Suma zobowiązań (Ty jesteś winien innym)
        # Bierzemy pod uwagę rozliczenia, gdzie user_id jest wierzycielem lub dłużnikiem.
        # W modelu Settlement są pola `debtor_user_id`, `creditor_user_id`
        # oraz `debtor_friend_id`, `creditor_friend_id`.
        # Poniższe zapytanie skupia się na rozliczeniach, gdzie UŻYTKOWNIK jest bezpośrednio stroną.
        # Jeśli rozliczenia z przyjaciółmi są reprezentowane przez Friend.user_id = current_user.id,
        # to logika może być bardziej złożona lub wymagać dodatkowych zapytań/joins.
        # Na razie zakładamy bezpośrednie rozliczenia między User-User.

        # Suma należności (Ty jesteś wierzycielem)
        creditor_sum = db.session.query(func.sum(Settlement.amount)).filter(
            Settlement.creditor_user_id == user_id
        ).scalar() or Decimal('0.00')

        # Suma zobowiązań (Ty jesteś dłużnikiem)
        debtor_sum = db.session.query(func.sum(Settlement.amount)).filter(
            Settlement.debtor_user_id == user_id
        ).scalar() or Decimal('0.00')

        total_balance = creditor_sum - debtor_sum

        # 2. Szczegółowe salda (kto komu jest winien/jesteś winien)
        # Rozliczenia, gdzie inni użytkownicy są dłużnikami wobec Ciebie
        owed_to_you = db.session.query(
            User.username, func.sum(Settlement.amount)
        ).join(Settlement, User.id == Settlement.debtor_user_id).filter(
            Settlement.creditor_user_id == user_id
        ).group_by(User.username).all()

        # Rozliczenia, gdzie znajomi są dłużnikami wobec Ciebie
        owed_to_you_friends = db.session.query(
            Friend.name, func.sum(Settlement.amount)
        ).join(Settlement, Friend.id == Settlement.debtor_friend_id).filter(
            Settlement.creditor_user_id == user_id
        ).group_by(Friend.name).all()

        for name, amount in owed_to_you:
            balances.append({'entity_name': name, 'amount': float(amount), 'type': 'owes_you'})
        for name, amount in owed_to_you_friends:
            balances.append({'entity_name': name, 'amount': float(amount), 'type': 'owes_you'})

        # Rozliczenia, gdzie Ty jesteś dłużnikiem wobec innych użytkowników
        you_owe = db.session.query(
            User.username, func.sum(Settlement.amount)
        ).join(Settlement, User.id == Settlement.creditor_user_id).filter(
            Settlement.debtor_user_id == user_id
        ).group_by(User.username).all()

        # Rozliczenia, gdzie Ty jesteś dłużnikiem wobec znajomych
        you_owe_friends = db.session.query(
            Friend.name, func.sum(Settlement.amount)
        ).join(Settlement, Friend.id == Settlement.creditor_friend_id).filter(
            Settlement.debtor_user_id == user_id
        ).group_by(Friend.name).all()

        for name, amount in you_owe:
            balances.append({'entity_name': name, 'amount': float(amount), 'type': 'you_owe'})
        for name, amount in you_owe_friends:
            balances.append({'entity_name': name, 'amount': float(amount), 'type': 'you_owe'})

        # 3. Wydatki na Listy Zakupów
        # Zgodnie z Product modelem, Product ma price (Numeric) i shopping_list_id
        # Nie ma kolumny quantity w Product, więc sumujemy tylko ceny.
        spending_data = db.session.query(
            ShoppingList.name, func.sum(Product.price)
        ).join(Product, ShoppingList.id == Product.shopping_list_id).group_by(ShoppingList.name).all()

        for list_name, total_spent in spending_data:
            spending_per_list[list_name] = float(total_spent or 0.0)

    except Exception as e:
        # Obsługa błędów, jeśli coś pójdzie nie tak z bazą danych
        print(f"Błąd podczas pobierania statystyk rozliczeń: {e}")
        return jsonify({'error': 'Nie udało się pobrać statystyk rozliczeń'}, 500)

    return jsonify({
        'total_balance': float(total_balance),
        'balances': balances,
        'spending_per_list': spending_per_list
    })


@bp.route('/api/activity')
@login_required
def get_settlement_activity():
    """
    API endpoint zwracający dane o aktywności rozliczeń (liczba rozliczeń na miesiąc).
    """
    user_id = current_user.id
    monthly_activity = []

    try:
        # W Settlement jest kolumna 'created_at' typu DateTime
        # Używamy func.strftime dla SQLite lub func.to_char dla PostgreSQL/MySQL
        # Dla SQLite: '%Y-%m' to format 'YYYY-MM'
        activity_data = db.session.query(
            func.strftime('%Y-%m', Settlement.created_at),
            func.count(Settlement.id)
        ).filter(
            (Settlement.creditor_user_id == user_id) | (Settlement.debtor_user_id == user_id)
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
    """
    user_id = current_user.id
    trends_data = []

    try:
        # Obliczanie trendów salda wymaga bardziej złożonej logiki,
        # ponieważ saldo jest sumą wszystkich rozliczeń do danego punktu w czasie.
        # Będziemy symulować to, pobierając wszystkie rozliczenia użytkownika
        # i agregując je tygodniowo.

        # Pobierz wszystkie rozliczenia dla danego użytkownika, posortowane chronologicznie
        all_settlements = db.session.query(Settlement).filter(
            (Settlement.creditor_user_id == user_id) | (Settlement.debtor_user_id == user_id)
        ).order_by(Settlement.created_at).all()

        current_balance = Decimal('0.00')
        weekly_balances = defaultdict(Decimal)  # Używamy defaultdict do przechowywania salda na koniec każdego tygodnia

        # Iteruj przez rozliczenia i aktualizuj saldo
        for settlement in all_settlements:
            if settlement.creditor_user_id == user_id:
                current_balance += settlement.amount
            elif settlement.debtor_user_id == user_id:
                current_balance -= settlement.amount

            # Ustaw saldo dla tygodnia, w którym rozliczenie zostało utworzone
            # Na koniec tygodnia saldo jest równe sumie wszystkich transakcji do tego momentu
            # datetime.isocalendar() zwraca (year, week_number, day_of_week)
            year, week_num, _ = settlement.created_at.isocalendar()
            week_key = f"{year}-{week_num:02d}"  # Format 'YYYY-WW'

            weekly_balances[week_key] = current_balance  # Zapisz saldo na koniec tygodnia

        # Generowanie danych dla ostatnich 12 tygodni (wstecz od bieżącego tygodnia)
        end_date = datetime.now()
        for i in range(12):
            week_date = end_date - timedelta(weeks=i)
            year, week_num, _ = week_date.isocalendar()
            week_key = f"{year}-{week_num:02d}"

            # Oblicz datę początku tygodnia (dla etykiety)
            # isocalendar zwraca poniedziałek jako 1, niedziela jako 7.
            # timedelta(days=weekday) daje nam początek bieżącego tygodnia (poniedziałek)
            # Weekday w isocalendar jest 1-indexed (1=Pon, ..., 7=Niedz).
            # Python's weekday() jest 0-indexed (0=Pon, ..., 6=Niedz).
            # Aby uzyskać początek tygodnia (poniedziałek) z daty:
            start_of_week = week_date - timedelta(days=week_date.weekday())
            week_label = start_of_week.strftime('%Y-%m-%d')  # Etykieta 'RRRR-MM-DD'

            # Pobierz saldo z defaultdict (jeśli brak, to 0)
            balance_for_week = weekly_balances.get(week_key, Decimal('0.00'))

            trends_data.insert(0, {  # Dodaj na początek listy, aby były chronologicznie
                'week': week_label,
                'total_amount': float(balance_for_week)
            })

    except Exception as e:
        print(f"Błąd podczas pobierania trendów rozliczeń: {e}")
        return jsonify({'error': 'Nie udało się pobrać trendów rozliczeń'}, 500)

    return jsonify({'trends': trends_data})

# Pamiętaj, aby zarejestrować blueprint 'bp' w main.py (jeśli jeszcze tego nie zrobiłeś)
# np. app.register_blueprint(bp)