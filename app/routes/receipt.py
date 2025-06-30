import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList, Friend, Product

receipt_bp = Blueprint('receipt', __name__, url_prefix='/lists_edition')


@receipt_bp.route('/', methods=['GET', 'POST'])  # Zmieniono na obsługę GET i POST
@receipt_bp.route('/<int:list_id>', methods=['GET', 'POST'])  # Zmieniono na obsługę GET i POST
@login_required
def lists_edition(list_id=None):
    # --- Obsługa żądania POST (zapisywanie/aktualizowanie listy) ---
    if request.method == 'POST':
        list_name = request.form.get('list_name')
        # Pobierz wartość z radio buttona
        status_str = request.form.get('is_fully_settled')
        # Konwertuj string 'True' na boolean True, a 'False' na boolean False
        is_fully_settled = status_str == 'True' if status_str else False  # Domyślnie na False jeśli brak wyboru

        products_data = []

        # Produkty są przesyłane jako products[index][name], products[index][price], products[index][friends][]
        # Musimy przetworzyć dane ręcznie dla złożonych struktur z indeksami.
        indexed_products = {}
        for key, value in request.form.items():
            if key.startswith('products['):
                parts = key.split('[')
                index = int(parts[1][:-1])  # Wyciągnij indeks, np. '0' z 'products[0]'
                field = parts[2][:-1]  # Wyciągnij pole, np. 'name' z '[name]'

                if index not in indexed_products:
                    indexed_products[index] = {'assigned_friends': []}

                if field == 'friends':
                    # Zbieraj wszystkie ID znajomych dla danego produktu
                    indexed_products[index]['assigned_friends'].append(int(value))
                else:
                    indexed_products[index][field] = value

        # Konwertuj słownik indeksów na listę produktów
        products_data = list(indexed_products.values())

        if list_id:
            # Edycja istniejącej listy
            shopping_list = ShoppingList.query.filter_by(id=list_id, created_by=current_user.id).first()
            if not shopping_list:
                flash('Lista zakupów nie została znaleziona lub nie masz do niej uprawnień.', 'danger')
                return redirect(url_for('main.dashboard'))  # Przekierowanie na dashboard z błędem

            shopping_list.name = list_name
            shopping_list.is_fully_settled = is_fully_settled  # Zapisz status
            flash('Lista zakupów została zaktualizowana!', 'success')
        else:
            # Tworzenie nowej listy
            shopping_list = ShoppingList(name=list_name, created_by=current_user.id,
                                         is_fully_settled=is_fully_settled)  # Zapisz status
            db.session.add(shopping_list)
            flash('Nowa lista zakupów została utworzona!', 'success')

        try:
            db.session.commit()  # Commit tutaj, aby shopping_list.id było dostępne dla produktów

            # Obsługa produktów
            # Lista ID produktów przesłanych w formularzu
            submitted_product_ids = [int(p['id']) for p in products_data if 'id' in p and p['id']]

            # Usuń produkty, które zostały usunięte z formularza (nie ma ich w submitted_product_ids)
            # Użyj .all() aby załadować relację przed iteracją i modyfikacją
            for product in shopping_list.products.all():
                if product.id not in submitted_product_ids:
                    db.session.delete(product)
            db.session.commit()  # Zatwierdź usunięcia przed dodawaniem nowych, by uniknąć konfliktów

            # Dodaj/zaktualizuj produkty
            for product_data in products_data:
                product_id = product_data.get('id')
                product_name = product_data.get('name')
                product_price = product_data.get('price')

                # Konwersja ceny na odpowiedni typ (Decimal)
                try:
                    product_price = float(product_price)
                except (ValueError, TypeError):
                    flash(
                        f"Nieprawidłowa cena dla produktu '{product_name}'. Upewnij się, że używasz kropki jako separatora dziesiętnego.",
                        'danger')
                    db.session.rollback()
                    # Ważne: przy błędzie musimy przekierować z powrotem na stronę edycji
                    # i opcjonalnie przekazać dotychczasowe dane, żeby użytkownik nie tracił pracy.
                    # Na potrzeby tego przykładu, po prostu wracamy.
                    return redirect(url_for('receipt.lists_edition', list_id=list_id or ''))

                if product_id:
                    # Edycja istniejącego produktu
                    product = Product.query.get(product_id)
                    if product and product.shopping_list_id == shopping_list.id:
                        product.name = product_name
                        product.price = product_price
                    else:
                        flash(f"Produkt o ID {product_id} nie znaleziono lub nie należy do tej listy.", 'warning')
                        continue
                else:
                    # Dodanie nowego produktu
                    product = Product(name=product_name, price=product_price, shopping_list_id=shopping_list.id)
                    db.session.add(product)

                db.session.flush()  # Upewnij się, że produkt ma ID przed przypisaniem znajomych, jeśli jest nowy

                # Zarządzanie przypisanymi znajomymi (relacja Many-to-Many)
                # Wyczyść istniejące przypisania i dodaj nowe
                product.assigned_friends_for_product.clear()
                for friend_id in product_data.get('assigned_friends', []):
                    friend = Friend.query.get(friend_id)
                    if friend and friend.user_id == current_user.id:  # Upewnij się, że znajomy należy do bieżącego użytkownika
                        product.assigned_friends_for_product.append(friend)

            db.session.commit()
            flash('Lista zakupów została pomyślnie zapisana!', 'success')
            return redirect(url_for('main.dashboard'))  # Przekieruj na dashboard po zapisie

        except Exception as e:
            db.session.rollback()
            flash(f'Wystąpił błąd podczas zapisywania listy zakupów: {e}', 'danger')
            # Przy błędzie wróć na stronę edycji, zachowując list_id
            return redirect(url_for('recipt.lists_edition', list_id=list_id or ''))

    # --- Obsługa żądania GET (wyświetlanie formularza) ---
    else:  # request.method == 'GET'
        shopping_list_data = []
        list_name = ""
        current_list_is_fully_settled = False  # Domyślna wartość dla nowej listy

        if list_id:
            current_list = ShoppingList.query.filter_by(id=list_id, created_by=current_user.id).first()
            if current_list:
                list_name = current_list.name
                current_list_is_fully_settled = current_list.is_fully_settled  # Pobierz status z bazy danych
                for product in current_list.products:
                    assigned_friends_ids = [friend.id for friend in product.assigned_friends_for_product]
                    shopping_list_data.append({
                        'id': product.id,
                        'name': product.name,
                        'price': float(product.price),  # Przekształć Decimal na float dla JSON
                        'assigned_friends': assigned_friends_ids
                    })
            else:
                flash('Lista zakupów o podanym ID nie została znaleziona lub nie masz do niej dostępu.', 'danger')
                return redirect(url_for('main.dashboard'))

        # Przygotuj dane znajomych z bazy danych
        all_friends_data = [{'id': friend.id, 'name': friend.name} for friend in current_user.friends_owned.all()]

        return render_template(
            'recipt/lists_edition.html',  # Sprawdź, czy nazwa szablonu to 'lists_edition.html' czy 'recipt/lists_edition.html'
            shopping_list_items=json.dumps(shopping_list_data),
            all_friends=json.dumps(all_friends_data),
            list_id=list_id,
            list_name=list_name,
            current_list_is_fully_settled=current_list_is_fully_settled  # Przekaż status do szablonu
        )


@receipt_bp.route('/delete-shopping-list/<int:list_id>', methods=['POST'])
@login_required
def delete_shopping_list(list_id):
    shopping_list_to_delete = ShoppingList.query.get_or_404(list_id)
    if shopping_list_to_delete.created_by != current_user.id:
        flash('Nie masz uprawnień do usunięcia tej listy.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        db.session.delete(shopping_list_to_delete)
        db.session.commit()
        flash('Lista zakupów została pomyślnie usunięta!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Błąd podczas usuwania listy zakupów: {e}', 'danger')

    return redirect(url_for('main.dashboard'))