# app/services/settlement_service.py

from decimal import Decimal, ROUND_HALF_UP  # Importujemy Decimal dla dokładnych obliczeń finansowych
from app import db  # Importujemy instancję bazy danych
from app.models import Product, ShoppingList, Settlement  # Importujemy potrzebne modele


def calculate_settlements(shopping_list_id):
    """
    Oblicza i zapisuje rozliczenia dla danej listy zakupów, minimalizując liczbę transakcji.

    Args:
        shopping_list_id (int): ID listy zakupów, dla której mają zostać obliczone rozliczenia.

    Returns:
        list: Lista obiektów Settlement, które zostały utworzone.
        None: Jeśli lista zakupów nie istnieje.
    """
    shopping_list = ShoppingList.query.get(shopping_list_id)
    if not shopping_list:
        print(f"ERROR: Lista zakupów o ID {shopping_list_id} nie została znaleziona.")
        return []  # Zwracamy pustą listę zamiast None

    products = Product.query.filter_by(shopping_list_id=shopping_list_id).all()
    participants = shopping_list.participants.all()  # Pobieramy wszystkich uczestników listy

    # Jeśli nie ma produktów lub uczestników, nie ma nic do rozliczania
    if not products or not participants:
        print(f"Brak produktów lub uczestników dla listy {shopping_list_id}. Brak rozliczeń do wygenerowania.")
        return []

    # Inicjalizacja sald dla wszystkich uczestników
    balances = {participant.id: Decimal('0.00') for participant in participants}

    # Obliczanie, kto ile zapłacił i ile jest mu przypisane
    # Najpierw sumujemy wpłaty (kto ile zapłacił za produkty)
    for product in products:
        if product.paid_by:
            # Każdy, kto zapłacił, ma zwiększone saldo
            balances[product.paid_by] += product.price

    # Następnie rozliczamy koszty produktów
    for product in products:
        item_price = product.price

        if product.assigned_to:
            # Jeśli produkt jest przypisany do konkretnej osoby, ta osoba płaci całą cenę
            if product.assigned_to in balances:  # Upewnij się, że przypisana osoba jest uczestnikiem
                balances[product.assigned_to] -= item_price
            else:
                print(
                    f"WARNING: Produkt {product.name} jest przypisany do użytkownika {product.assigned_to}, który nie jest uczestnikiem listy {shopping_list_id}. Koszt nie zostanie przypisany (błąd danych?).")
        else:
            # Jeśli produkt nie jest przypisany do nikogo, jego koszt ponosi osoba, która za niego zapłaciła.
            # Poprzednio: dzielono równo między wszystkich uczestników.
            if product.paid_by in balances:  # Upewnij się, że płacący jest uczestnikiem
                balances[product.paid_by] -= item_price
            else:
                # Ten przypadek oznacza, że produkt nie jest przypisany i został zapłacony przez kogoś, kto nie jest uczestnikiem listy.
                # W praktyce powinien być przypisany albo do uczestnika, albo płacący powinien być uczestnikiem.
                print(
                    f"WARNING: Produkt {product.name} (ID {product.id}) nie jest przypisany i został zapłacony przez użytkownika {product.paid_by}, który nie jest uczestnikiem listy {shopping_list_id}. Koszt nie zostanie rozliczony.")

    # Filtrowanie sald zerowych i zaokrąglanie do dwóch miejsc po przecinku
    # Używamy ROUND_HALF_UP dla standardowego zaokrąglania bankowego
    balances = {uid: balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                for uid, balance in balances.items() if balance != Decimal('0.00')}

    # Podział na dłużników i wierzycieli
    debtors = {uid: abs(balance) for uid, balance in balances.items() if balance < 0}
    creditors = {uid: balance for uid, balance in balances.items() if balance > 0}

    # Konwersja na listy słowników i sortowanie (dla algorytmu minimalizacji)
    # Dłużnicy: od największego długu do najmniejszego
    # Wierzyciele: od największej kwoty do odzyskania do najmniejszej
    debtors_list = sorted([{'id': uid, 'amount': amount} for uid, amount in debtors.items()], key=lambda x: x['amount'],
                          reverse=True)
    creditors_list = sorted([{'id': uid, 'amount': amount} for uid, amount in creditors.items()],
                            key=lambda x: x['amount'], reverse=True)

    generated_settlements = []

    # Algorytm minimalizujący liczbę transakcji (Debtor-Creditor Matching)
    while debtors_list and creditors_list:
        debtor = debtors_list[0]
        creditor = creditors_list[0]

        # Kwota do uregulowania w tej transakcji
        amount_to_settle = min(debtor['amount'], creditor['amount'])

        # Tworzenie obiektu rozliczenia
        new_settlement = Settlement(
            shopping_list_id=shopping_list_id,
            debtor_id=debtor['id'],
            creditor_id=creditor['id'],
            amount=amount_to_settle,
            is_settled=False
        )
        generated_settlements.append(new_settlement)
        db.session.add(new_settlement)

        # Aktualizacja sald
        debtor['amount'] -= amount_to_settle
        creditor['amount'] -= amount_to_settle

        # Usuwanie dłużników/wierzycieli, których saldo zostało całkowicie uregulowane
        if debtor['amount'] == Decimal('0.00'):
            debtors_list.pop(0)
        if creditor['amount'] == Decimal('0.00'):
            creditors_list.pop(0)

    # Zapis rozliczeń do bazy danych
    try:
        db.session.commit()
        print(f"Wygenerowano {len(generated_settlements)} rozliczeń dla listy {shopping_list_id}.")
        return generated_settlements
    except Exception as e:
        db.session.rollback()
        print(f"Błąd podczas zapisu rozliczeń dla listy {shopping_list_id}: {e}")
        return []

