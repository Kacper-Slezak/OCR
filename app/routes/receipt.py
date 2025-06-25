import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db # Zakładam, że 'db' jest Twoim obiektem SQLAlchemy
from app.models import Receipt # Zakładam, że 'Receipt' to Twój model, który będzie przechowywał listę zakupów
# Jeśli masz osobny model dla listy zakupów, np. ShoppingList, użyj go zamiast Receipt

receipt_bp = Blueprint('receipt', __name__, url_prefix='/lists_edition')

# --- Mock danych znajomych (w prawdziwej aplikacji pobieraj z bazy danych) ---
# Przykład struktury: {'id': 'friend1', 'name': 'Alicja'}
MOCK_ALL_FRIENDS = [
    {'id': 'friend1', 'name': 'Alicja'},
    {'id': 'friend2', 'name': 'Bartek'},
    {'id': 'friend3', 'name': 'Celina'},
    {'id': 'friend4', 'name': 'Dawid'},
    {'id': 'friend5', 'name': 'Ewa'}
]
# -------------------------------------------------------------------------

@receipt_bp.route('/', methods=['GET'])
@receipt_bp.route('/<int:list_id>', methods=['GET'])
@login_required
def edit_shopping_list(list_id=None):
    """
    Endpoint do wyświetlania lub tworzenia listy zakupów.
    Jeśli list_id jest None, próbuje załadować domyślną listę użytkownika lub tworzy pustą.
    """
    shopping_list_data = [] # Domyślna pusta lista
    current_list = None
    list_title = "Nowa Lista Zakupów"

    if list_id:
        # Próba załadowania konkretnej listy po ID
        current_list = Receipt.query.filter_by(id=list_id, user_id=current_user.id).first()
        if current_list:
            # Zakładamy, że processed_data zawiera listę produktów
            shopping_list_data = current_list.processed_data if current_list.processed_data else []
            list_title = f"Edytuj Listę ID: {current_list.id}"
        else:
            flash('Lista zakupów o podanym ID nie została znaleziona lub nie masz do niej dostępu.', 'error')
            return redirect(url_for('recipt.edit_shopping_list')) # Przekieruj na stronę tworzenia nowej listy

    # W przypadku braku list_id (route '/'), można by tu dodać logikę pobierania "domyślnej" listy użytkownika,
    # np. pierwszej listy, którą kiedykolwiek stworzył, lub listy oznaczonej jako domyślna.
    # Na potrzeby tego przykładu, jeśli nie ma list_id, po prostu tworzymy pustą listę do edycji.

    return render_template(
        '/recipt/lists_edition.html', # Upewnij się, że ścieżka do szablonu jest poprawna
        shopping_list_items=shopping_list_data,
        all_friends=MOCK_ALL_FRIENDS,
        list_id=list_id, # Przekaż ID listy do szablonu, aby formularz mógł je odesłać
        list_title=list_title
    )

@receipt_bp.route('/save', methods=['POST'])
@login_required
def save_shopping_list():
    """
    Endpoint do zapisywania (tworzenia/aktualizowania) listy zakupów.
    """
    list_id = request.form.get('list_id') # Pobierz ID listy z ukrytego pola formularza
    products_data = []

    # Iteruj przez dane formularza, aby znaleźć produkty i przypisanych znajomych
    # Formularz wysyła dane w formacie: products[0][name], products[0][friends][], products[1][name], itd.
    # Musimy znaleźć unikalne indeksy produktów.
    product_indices = sorted(list(set([
        int(k.split('[')[1].split(']')[0])
        for k in request.form if k.startswith('products[') and '][' in k
    ])))

    for i in product_indices:
        product_name = request.form.get(f'products[{i}][name]')
        assigned_friends = request.form.getlist(f'products[{i}][friends][]') # Użyj getlist dla checkboxów

        if product_name: # Tylko dodaj produkt, jeśli ma nazwę
            products_data.append({
                'name': product_name,
                'assigned_friends': assigned_friends
            })

    if list_id:
        # Edycja istniejącej listy
        current_list = Receipt.query.filter_by(id=list_id, user_id=current_user.id).first()
        if current_list:
            current_list.processed_data = products_data # Zapisz zaktualizowane dane
            flash('Lista zakupów została zaktualizowana!', 'success')
        else:
            flash('Błąd: Nie znaleziono listy do aktualizacji lub nie masz do niej dostępu.', 'error')
            return redirect(url_for('receipt.edit_shopping_list')) # Przekieruj na stronę tworzenia nowej listy
    else:
        # Tworzenie nowej listy
        new_list = Receipt(user_id=current_user.id, processed_data=products_data)
        db.session.add(new_list)
        flash('Nowa lista zakupów została utworzona!', 'success')

    db.session.commit()
    # Po zapisaniu, możesz przekierować użytkownika z powrotem do edycji listy (jeśli istnieje)
    # lub na ogólną stronę z listami. Tutaj przekierowuję na stronę główną blueprintu.
    if list_id:
        return redirect(url_for('receipt.edit_shopping_list', list_id=list_id))
    else:
        # Jeśli to była nowa lista, możesz przekierować do jej edycji z nowym ID
        # (co wymagałoby odświeżenia obiektu new_list, żeby poznać jego ID)
        # Lub po prostu na ogólną stronę /lists_edition/
        return redirect(url_for('receipt.edit_shopping_list'))
