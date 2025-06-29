# app/services/settlement_service.py

from decimal import Decimal, ROUND_HALF_UP
from app import db
from app.models import Product, User, ShoppingList, Settlement, Friend


def calculate_settlements(shopping_list_id):
    """
    Oblicza i zapisuje rozliczenia dla danej listy zakupów, minimalizując liczbę transakcji.
    Rozliczenia mogą odbywać się między Użytkownikami a Znajomymi.

    Args:
        shopping_list_id (int): ID listy zakupów, dla której mają zostać obliczone rozliczenia.

    Returns:
        list: Lista obiektów Settlement, które zostały utworzone.
        None: Jeśli lista zakupów nie istnieje.
    """
    shopping_list = ShoppingList.query.get(shopping_list_id)
    if not shopping_list:
        print(f"ERROR: Lista zakupów o ID {shopping_list_id} nie została znaleziona.")
        return []

    products = Product.query.filter_by(shopping_list_id=shopping_list_id).all()
    # Pobieramy wszystkich uczestników listy (Users)
    participants = shopping_list.participants.all()
    # Pobieramy wszystkich znajomych, którzy są przypisani do produktów na tej liście
    # Znajomi są właścicielami przez User, ale mogą być przypisani do produktów niezależnie.
    # W kontekście rozliczeń, interesują nas znajomi, którzy faktycznie coś "nabyli".
    # Możemy zidentyfikować ich poprzez product.assigned_friends_for_product.

    # Zbieramy wszystkie unikalne podmioty (Users i Friends) zaangażowane w płatności/przypisania na tej liście
    # Używamy formatu klucza (typ_podmiotu, id_podmiotu)
    all_entities = set()
    for participant in participants:
        all_entities.add(('user', participant.id))

    for product in products:
        if product.paid_by:
            all_entities.add(('user', product.paid_by))
        for friend in product.assigned_friends_for_product:
            all_entities.add(('friend', friend.id))

    if not products or not all_entities:  # Sprawdzamy, czy w ogóle są podmioty do rozliczeń
        print(
            f"Brak produktów lub podmiotów do rozliczeń dla listy {shopping_list_id}. Brak rozliczeń do wygenerowania.")
        return []

    # Inicjalizacja sald dla wszystkich zaangażowanych podmiotów (User i Friend)
    # Klucze to krotki (typ_podmiotu, id_podmiotu)
    balances = {entity: Decimal('0.00') for entity in all_entities}

    # Sumujemy wpłaty (kto ile zapłacił za produkty)
    for product in products:
        if product.paid_by:
            # Płacący to zawsze User
            balances[('user', product.paid_by)] += product.price

    # Rozliczamy koszty produktów
    for product in products:
        item_price = product.price

        assigned_friends = product.assigned_friends_for_product.all()

        if assigned_friends:
            # Jeśli produkt jest przypisany do jednego lub wielu ZNAJOMYCH,
            # koszt jest dzielony równo między nich.
            share_per_friend = item_price / Decimal(len(assigned_friends))
            for friend in assigned_friends:
                if ('friend', friend.id) in balances:
                    balances[('friend', friend.id)] -= share_per_friend
                else:
                    # To nie powinno się zdarzyć, jeśli all_entities jest poprawnie zbudowane
                    print(f"WARNING: Znajomy {friend.name} (ID {friend.id}) nie jest w balansie. Błąd logiki.")
        else:
            # Jeśli produkt nie jest przypisany do żadnych znajomych,
            # jego koszt ponosi osoba, która za niego zapłaciła (User).
            if product.paid_by:  # Product.paid_by jest User ID
                if ('user', product.paid_by) in balances:
                    balances[('user', product.paid_by)] -= item_price
                else:
                    print(
                        f"WARNING: Produkt {product.name} (ID {product.id}) nie jest przypisany i został zapłacony przez użytkownika {product.paid_by}, który nie jest w balansie. Koszt nie zostanie rozliczony.")
            else:
                print(
                    f"WARNING: Produkt {product.name} (ID {product.id}) nie jest przypisany i nie ma przypisanego płacącego. Koszt nie zostanie rozliczony.")

    # Filtrowanie sald zerowych i zaokrąglanie
    balances = {entity: balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                for entity, balance in balances.items() if balance != Decimal('0.00')}

    # Podział na dłużników i wierzycieli
    debtors = {entity: abs(balance) for entity, balance in balances.items() if balance < 0}
    creditors = {entity: balance for entity, balance in balances.items() if balance > 0}

    # Konwersja na listy słowników i sortowanie
    # Teraz zawierają (typ_podmiotu, id_podmiotu)
    debtors_list = sorted([{'entity': entity, 'amount': amount} for entity, amount in debtors.items()],
                          key=lambda x: x['amount'], reverse=True)
    creditors_list = sorted([{'entity': entity, 'amount': amount} for entity, amount in creditors.items()],
                            key=lambda x: x['amount'], reverse=True)

    generated_settlements = []

    # Algorytm minimalizujący liczbę transakcji (Debtor-Creditor Matching)
    while debtors_list and creditors_list:
        debtor_item = debtors_list[0]
        creditor_item = creditors_list[0]

        amount_to_settle = min(debtor_item['amount'], creditor_item['amount'])

        new_settlement = Settlement(
            shopping_list_id=shopping_list_id,
            amount=amount_to_settle,
            is_settled=False
        )

        # Ustawienie pól dłużnika
        if debtor_item['entity'][0] == 'user':
            new_settlement.debtor_user_id = debtor_item['entity'][1]
        else:  # 'friend'
            new_settlement.debtor_friend_id = debtor_item['entity'][1]

        # Ustawienie pól wierzyciela
        if creditor_item['entity'][0] == 'user':
            new_settlement.creditor_user_id = creditor_item['entity'][1]
        else:  # 'friend'
            new_settlement.creditor_friend_id = creditor_item['entity'][1]

        generated_settlements.append(new_settlement)
        db.session.add(new_settlement)

        # Aktualizacja sald w listach
        debtor_item['amount'] -= amount_to_settle
        creditor_item['amount'] -= amount_to_settle

        if debtor_item['amount'] == Decimal('0.00'):
            debtors_list.pop(0)
        if creditor_item['amount'] == Decimal('0.00'):
            creditors_list.pop(0)

    try:
        db.session.commit()
        print(f"Wygenerowano {len(generated_settlements)} rozliczeń dla listy {shopping_list_id}.")
        return generated_settlements
    except Exception as e:
        db.session.rollback()
        print(f"Błąd podczas zapisu rozliczeń dla listy {shopping_list_id}: {e}")
        return []
