# app/services/settlement_service.py

from decimal import Decimal, ROUND_HALF_UP
from app import db
from app.models import Product, ShoppingList, Settlement, User  # Upewnij się, że User i Friend są zaimportowane


def check_and_update_list_settlement_status(shopping_list_id):
    """
    Sprawdza, czy wszystkie rozliczenia dla danej listy zakupów zostały uregulowane.
    Jeśli tak, ustawia is_fully_settled na True dla ShoppingList.
    """
    shopping_list = ShoppingList.query.get(shopping_list_id)
    if not shopping_list:
        print(
            f"DEBUG: _check_and_update_list_settlement_status: Błąd: Lista zakupów o ID {shopping_list_id} nie istnieje.")
        return

    all_list_settlements = Settlement.query.filter_by(shopping_list_id=shopping_list_id).all()
    all_settled = all(s.is_settled for s in all_list_settlements) if all_list_settlements else True

    if all_settled and not shopping_list.is_fully_settled:
        shopping_list.is_fully_settled = True
        print(
            f"DEBUG: _check_and_update_list_settlement_status: Lista '{shopping_list.name}' (ID: {shopping_list_id}) została w pełni rozliczona.")
    elif not all_settled and shopping_list.is_fully_settled:
        shopping_list.is_fully_settled = False
        print(
            f"DEBUG: _check_and_update_list_settlement_status: Lista '{shopping_list.name}' (ID: {shopping_list_id}) NIE jest w pełni rozliczona. Zmieniono status.")

    db.session.commit()
    print(f"DEBUG: _check_and_update_list_settlement_status: Zmiany statusu listy {shopping_list_id} zatwierdzone.")


def calculate_settlements(shopping_list_id):
    """
    Oblicza i zapisuje rozliczenia dla danej listy zakupów, minimalizując liczbę transakcji.
    Rozliczenia mogą odbywać się między Użytkownikami a Znajomymi.
    """
    shopping_list = ShoppingList.query.get(shopping_list_id)
    if not shopping_list:
        print(f"DEBUG: calculate_settlements: ERROR: Lista zakupów o ID {shopping_list_id} nie została znaleziona.")
        return []

    products = Product.query.filter_by(shopping_list_id=shopping_list_id).all()
    print(f"DEBUG: calculate_settlements: Produkty dla listy {shopping_list_id}: {[p.name for p in products]}")

    participants = shopping_list.participants.all()
    print(f"DEBUG: calculate_settlements: Uczestnicy listy {shopping_list_id}: {[p.username for p in participants]}")

    all_entities = set()
    for participant in participants:
        all_entities.add(('user', participant.id))

    for product in products:
        if product.paid_by:
            all_entities.add(('user', product.paid_by))
        for friend in product.assigned_friends_for_product:
            all_entities.add(('friend', friend.id))

    print(f"DEBUG: calculate_settlements: Wszystkie zaangażowane podmioty: {all_entities}")

    if not products or not all_entities:
        print(
            f"DEBUG: calculate_settlements: Brak produktów lub podmiotów do rozliczeń dla listy {shopping_list_id}. Brak rozliczeń do wygenerowania.")
        shopping_list.is_fully_settled = True
        db.session.commit()
        return []

    balances = {entity: Decimal('0.00') for entity in all_entities}
    print(f"DEBUG: calculate_settlements: Salda początkowe: {balances}")

    # Sumujemy wpłaty (kto ile zapłacił za produkty)
    for product in products:
        if product.paid_by:
            balances[('user', product.paid_by)] += product.price
            print(
                f"DEBUG: calculate_settlements: Użytkownik {User.query.get(product.paid_by).username if User.query.get(product.paid_by) else product.paid_by} zapłacił {product.price} za {product.name}. Nowe saldo: {balances[('user', product.paid_by)]}")
    print(f"DEBUG: calculate_settlements: Salda po sumowaniu wpłat: {balances}")

    # Rozliczamy koszty produktów
    for product in products:
        item_price = product.price
        assigned_friends = product.assigned_friends_for_product

        if assigned_friends:
            share_per_friend = item_price / Decimal(len(assigned_friends))
            for friend in assigned_friends:
                if ('friend', friend.id) in balances:
                    balances[('friend', friend.id)] -= share_per_friend
                    print(
                        f"DEBUG: calculate_settlements: Znajomy {friend.name} przypisany do {product.name}. Saldo: {balances[('friend', friend.id)]}")
                else:
                    print(
                        f"DEBUG: calculate_settlements: WARNING: Znajomy {friend.name} (ID {friend.id}) nie jest w balansie. Błąd logiki.")
        else:
            if product.paid_by:
                if ('user', product.paid_by) in balances:
                    balances[('user', product.paid_by)] -= item_price
                    print(
                        f"DEBUG: calculate_settlements: Użytkownik {User.query.get(product.paid_by).username if User.query.get(product.paid_by) else product.paid_by} ponosi koszt {item_price} za {product.name}. Saldo: {balances[('user', product.paid_by)]}")
                else:
                    print(
                        f"DEBUG: calculate_settlements: WARNING: Produkt {product.name} (ID {product.id}) nie jest przypisany i został zapłacony przez użytkownika {product.paid_by}, który nie jest w balansie. Koszt nie zostanie rozliczony.")
            else:
                print(
                    f"DEBUG: calculate_settlements: WARNING: Produkt {product.name} (ID {product.id}) nie jest przypisany i nie ma przypisanego płacącego. Koszt nie zostanie rozliczony.")

    print(f"DEBUG: calculate_settlements: Salda po rozliczeniu kosztów: {balances}")

    balances = {entity: balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                for entity, balance in balances.items() if balance != Decimal('0.00')}
    print(f"DEBUG: calculate_settlements: Salda po zaokrągleniu i odfiltrowaniu zerowych: {balances}")

    debtors = {entity: abs(balance) for entity, balance in balances.items() if balance < 0}
    creditors = {entity: balance for entity, balance in balances.items() if balance > 0}

    debtors_list = sorted([{'entity': entity, 'amount': amount} for entity, amount in debtors.items()],
                          key=lambda x: x['amount'], reverse=True)
    creditors_list = sorted([{'entity': entity, 'amount': amount} for entity, amount in creditors.items()],
                            key=lambda x: x['amount'], reverse=True)

    print(f"DEBUG: calculate_settlements: Lista dłużników: {debtors_list}")
    print(f"DEBUG: calculate_settlements: Lista wierzycieli: {creditors_list}")

    generated_settlements = []

    while debtors_list and creditors_list:
        debtor_item = debtors_list[0]
        creditor_item = creditors_list[0]

        amount_to_settle = min(debtor_item['amount'], creditor_item['amount'])

        new_settlement = Settlement(
            shopping_list_id=shopping_list_id,
            amount=amount_to_settle,
            is_settled=False
        )

        if debtor_item['entity'][0] == 'user':
            new_settlement.debtor_user_id = debtor_item['entity'][1]
        else:  # 'friend'
            new_settlement.debtor_friend_id = debtor_item['entity'][1]

        if creditor_item['entity'][0] == 'user':
            new_settlement.creditor_user_id = creditor_item['entity'][1]
        else:  # 'friend'
            new_settlement.creditor_friend_id = creditor_item['entity'][1]

        generated_settlements.append(new_settlement)
        db.session.add(new_settlement)

        print(f"DEBUG: calculate_settlements: Dodano rozliczenie: {new_settlement}")

        debtor_item['amount'] -= amount_to_settle
        creditor_item['amount'] -= amount_to_settle

        if debtor_item['amount'] == Decimal('0.00'):
            debtors_list.pop(0)
        if creditor_item['amount'] == Decimal('0.00'):
            creditors_list.pop(0)

    try:
        db.session.commit()
        print(
            f"DEBUG: calculate_settlements: Wygenerowano {len(generated_settlements)} rozliczeń dla listy {shopping_list_id}.")
        check_and_update_list_settlement_status(shopping_list_id)
        return generated_settlements
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: calculate_settlements: Błąd podczas zapisu rozliczeń dla listy {shopping_list_id}: {e}")
        return []
