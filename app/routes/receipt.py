# app/routes/receipt.py

from flask import render_template, Blueprint, redirect, url_for, flash, request, current_app as app, send_file, \
    make_response, abort
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList, Product, Receipt, Friend, User  # Ensure User is imported for participants
from app.services.ocr_services import process_receipt_image  # Your existing OCR service
from app.services.merging_services import match_ocr_to_shopping_list  # Renamed from ocr_matching_service
from decimal import Decimal, InvalidOperation
import os
from werkzeug.utils import secure_filename
import io
import csv  # For CSV export

receipt_bp = Blueprint('receipt', __name__)


# --- Trasy dotyczące List Zakupów ---

@receipt_bp.route('/shopping-list/edit', defaults={'list_id': None}, methods=['GET', 'POST'])
@receipt_bp.route('/shopping-list/edit/<int:list_id>', methods=['GET', 'POST'])
@login_required
def edit_shopping_list(list_id):
    """
    Umożliwia tworzenie nowej listy zakupów lub edycję istniejącej.
    Obsługuje dodawanie/usuwanie produktów i przypisywanie znajomych.
    Zawiera formularz do wgrywania paragonów dla danej listy.
    """
    shopping_list = None
    if list_id:
        shopping_list = ShoppingList.query.get_or_404(list_id)
        # Sprawdź, czy użytkownik jest twórcą lub uczestnikiem
        if shopping_list.created_by != current_user.id and current_user not in shopping_list.participants.all():
            flash('Nie masz uprawnień do edycji tej listy zakupów.', 'danger')
            return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        list_name = request.form.get('list_name', '').strip()
        if not list_name:
            flash('Nazwa listy zakupów nie może być pusta!', 'danger')
            return redirect(
                url_for('receipt.edit_shopping_list', list_id=list_id) if list_id else url_for('main.dashboard'))

        if shopping_list:
            shopping_list.name = list_name
        else:
            shopping_list = ShoppingList(name=list_name, created_by=current_user.id)
            db.session.add(shopping_list)
            db.session.flush()  # Potrzebne do uzyskania ID dla nowej listy przed dodaniem produktów

        # Obsługa produktów z formularza
        products_data = []
        i = 0
        while f'products[{i}][name]' in request.form:
            product_name = request.form.get(f'products[{i}][name]', '').strip()
            product_price_str = request.form.get(f'products[{i}][price]', '').strip()
            assigned_friends_ids = request.form.getlist(f'products[{i}][assigned_friends][]')

            if product_name:  # Przetwarzaj tylko produkty z nazwą
                product_price = Decimal('0.00')
                if product_price_str:
                    try:
                        product_price = Decimal(product_price_str.replace(',', '.'))
                    except InvalidOperation:
                        flash(f'Nieprawidłowy format ceny dla produktu "{product_name}". Użyto 0.00.', 'warning')
                        product_price = Decimal('0.00')

                products_data.append({
                    'name': product_name,
                    'price': product_price,
                    'assigned_friends_ids': [int(fid) for fid in assigned_friends_ids if fid.isdigit()]
                })
            i += 1

        # Usuń istniejące produkty dla tej listy przed dodaniem nowych z formularza
        # To upraszcza aktualizacje, ale oznacza utratę historii produktów.
        if shopping_list.id:
            Product.query.filter_by(shopping_list_id=shopping_list.id).delete()
            db.session.flush()  # Upewnij się, że usunięcia są przetworzone przed dodaniem nowych produktów

        for p_data in products_data:
            new_product = Product(
                name=p_data['name'],
                price=p_data['price'],
                shopping_list_id=shopping_list.id,
                paid_by=current_user.id,  # Zakładamy, że aktualny użytkownik płaci
                is_purchased=False
            )
            db.session.add(new_product)
            db.session.flush()  # Flush, aby uzyskać ID produktu przed przypisaniem znajomych

            # Przypisz znajomych - Upewnij się, że dodajesz tylko UNIKALNE ID znajomych
            unique_friend_ids = set(p_data['assigned_friends_ids'])  # Użyj set dla unikalności
            for friend_id in unique_friend_ids:
                friend = Friend.query.get(friend_id)
                if friend and friend.user_id == current_user.id:  # Upewnij się, że znajomy należy do użytkownika
                    new_product.assigned_friends_for_product.append(friend)

        try:
            db.session.commit()
            flash('Lista zakupów została pomyślnie zapisana!', 'success')
            return redirect(url_for('receipt.edit_shopping_list', list_id=shopping_list.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Błąd podczas zapisywania listy zakupów: {e}', 'danger')
            return redirect(request.url)

    # Żądanie GET: Wyświetl formularz
    products_data = []
    if shopping_list:
        for product in shopping_list.products:
            products_data.append({
                'name': product.name,
                'price': product.price,  # Już Decimal
                'assigned_friends': [f.id for f in product.assigned_friends_for_product],
                'paid_by': product.paid_by,  # Uwzględnij paid_by
                'db_id': product.id
            })

    all_friends_for_user = current_user.friends_owned.all()
    all_friends_for_js = [{'id': friend.id, 'name': friend.name} for friend in all_friends_for_user]

    return render_template(
        'recipt/edit_shopping_list.html',  # Zmieniona nazwa szablonu
        shopping_list=shopping_list,
        products_data=products_data,
        all_friends=all_friends_for_js
    )


@receipt_bp.route('/shopping-list/delete/<int:list_id>', methods=['POST'])
@login_required
def delete_shopping_list(list_id):
    """
    Usuwa listę zakupów.
    """
    shopping_list = ShoppingList.query.get_or_404(list_id)
    if shopping_list.created_by != current_user.id:
        flash('Nie masz uprawnień do usunięcia tej listy zakupów.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        db.session.delete(shopping_list)
        db.session.commit()
        flash('Lista zakupów została pomyślnie usunięta!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Błąd podczas usuwania listy zakupów: {e}', 'danger')

    return redirect(url_for('main.dashboard'))


# --- Trasy dotyczące Paragonów i OCR ---

def allowed_file(filename):
    """Sprawdza, czy rozszerzenie pliku jest dozwolone."""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@receipt_bp.route('/receipt/upload/<int:list_id>', methods=['POST'])
@login_required
def upload_receipt_for_list(list_id):
    """
    Wgrywa obraz paragonu dla konkretnej listy zakupów i inicjuje proces OCR.
    """
    shopping_list = ShoppingList.query.get_or_404(list_id)
    if shopping_list.created_by != current_user.id:  # Tylko twórca może wgrywać paragony dla tej listy
        flash('Nie masz uprawnień do dodawania paragonów do tej listy.', 'danger')
        return redirect(url_for('main.dashboard'))

    if 'file' not in request.files:
        flash('Brak pliku w żądaniu.', 'warning')
        return redirect(url_for('receipt.edit_shopping_list', list_id=list_id))

    file = request.files['file']
    if file.filename == '':
        flash('Nie wybrano pliku.', 'warning')
        return redirect(url_for('receipt.edit_shopping_list', list_id=list_id))

    if file and allowed_file(file.filename):
        uploads_dir = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        os.makedirs(uploads_dir, exist_ok=True)
        filename = secure_filename(file.filename)
        file_path = os.path.join(uploads_dir, filename)
        file.save(file_path)

        new_receipt = Receipt(
            user_id=current_user.id,
            file_path=file_path,
            shopping_list_id=list_id,  # Powiąż paragon z listą zakupów!
            status='Uploaded'
        )
        db.session.add(new_receipt)
        db.session.commit()

        flash('Paragon został wgrany i jest przetwarzany.', 'info')

        # Uruchom OCR w tle (lub przekieruj na stronę oczekiwania)
        # Na razie wywołujemy bezpośrednio. W prawdziwej aplikacji użyj Celery/RQ.
        process_receipt_image(new_receipt.id, file_path)

        # Po przetworzeniu, przekieruj użytkownika na stronę przeglądu OCR
        return redirect(url_for('receipt.review_ocr_results', receipt_id=new_receipt.id))
    else:
        flash('Dozwolone typy plików to: png, jpg, jpeg, gif.', 'error')
        return redirect(url_for('receipt.edit_shopping_list', list_id=list_id))


@receipt_bp.route('/receipt/review/<int:receipt_id>', methods=['GET', 'POST'])
@login_required
def review_ocr_results(receipt_id):
    """
    Umożliwia przeglądanie i korygowanie wyników OCR dla paragonu.
    Po zatwierdzeniu, przekierowuje do scalania z listą zakupów.
    """
    receipt = Receipt.query.get_or_404(receipt_id)
    if receipt.user_id != current_user.id:
        flash('Nie masz uprawnień do przeglądania tego paragonu.', 'danger')
        return redirect(url_for('main.dashboard'))

    parsed_ocr_data = receipt.get_processed_data()

    if not parsed_ocr_data or "items" not in parsed_ocr_data:
        flash('Brak przetworzonych danych OCR lub dane są niekompletne. Spróbuj wgrać ponownie lub sprawdź usługę OCR.',
              'warning')
        redirect_url = url_for('main.dashboard')
        if receipt.shopping_list_id:
            redirect_url = url_for('receipt.edit_shopping_list', list_id=receipt.shopping_list_id)
        return redirect(redirect_url)

    if request.method == 'POST':
        corrected_ocr_items = []
        i = 0
        while f'ocr_items[{i}][name]' in request.form:
            name = request.form.get(f'ocr_items[{i}][name]', '').strip()
            total_price_str = request.form.get(f'ocr_items[{i}][total_price]', '').strip()

            if name:  # Dodawaj tylko elementy z nazwą
                price_decimal = Decimal('0.00')
                if total_price_str:
                    try:
                        price_decimal = Decimal(total_price_str.replace(',', '.'))
                    except InvalidOperation:
                        flash(f'Nieprawidłowy format ceny dla pozycji OCR "{name}". Użyto 0.00.', 'warning')
                        price_decimal = Decimal('0.00')

                corrected_ocr_items.append(
                    {'name': name, 'total_price': str(price_decimal)})  # Zapisz jako string dla JSON
            i += 1

        # Zapisz skorygowane dane z powrotem do receipt.processed_data
        parsed_ocr_data['items'] = corrected_ocr_items
        receipt.set_processed_data(parsed_ocr_data)
        db.session.commit()
        flash('Korekty OCR zapisane.', 'success')

        # Przejdź do scalania z listą zakupów
        return redirect(url_for('receipt.merge_ocr_with_list', receipt_id=receipt.id))

    # Żądanie GET: Wyświetl formularz korekty
    return render_template(
        'ocr/review_ocr_results.html',  # Nowy szablon
        receipt=receipt,
        ocr_items=parsed_ocr_data.get('items', [])
    )


@receipt_bp.route('/receipt/merge/<int:receipt_id>', methods=['GET'])
@login_required
def merge_ocr_with_list(receipt_id):
    """
    Scala dane z paragonu (po OCR) z produktami na powiązanej liście zakupów.
    """
    print(f"DEBUG: Rozpoczynanie scalania dla paragonu ID: {receipt_id}")
    receipt = Receipt.query.get_or_404(receipt_id)
    if receipt.user_id != current_user.id:
        flash('Nie masz uprawnień do scalania danych z tego paragonu.', 'danger')
        print(
            f"DEBUG: Błąd uprawnień dla paragonu ID: {receipt_id}. Użytkownik {current_user.id} nie jest właścicielem.")
        return redirect(url_for('main.dashboard'))

    if not receipt.shopping_list_id:
        flash('Ten paragon nie jest powiązany z żadną listą zakupów. Najpierw go powiąż.', 'warning')
        print(f"DEBUG: Paragon ID: {receipt_id} nie jest powiązany z listą zakupów.")
        return redirect(url_for('main.dashboard'))

    shopping_list = ShoppingList.query.get_or_404(receipt.shopping_list_id)
    # Sprawdź, czy użytkownik jest twórcą lub uczestnikiem listy
    if shopping_list.created_by != current_user.id and current_user not in shopping_list.participants.all():
        flash('Nie masz uprawnień do modyfikowania tej listy zakupów.', 'danger')
        print(
            f"DEBUG: Błąd uprawnień dla listy zakupów ID: {shopping_list.id}. Użytkownik {current_user.id} nie jest twórcą ani uczestnikiem.")
        return redirect(url_for('main.dashboard'))

    parsed_ocr_data = receipt.get_processed_data()
    if not parsed_ocr_data or "items" not in parsed_ocr_data:
        flash('Brak przetworzonych danych OCR do scalenia.', 'warning')
        print(f"DEBUG: Brak przetworzonych danych OCR dla paragonu ID: {receipt_id}.")
        return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

    print(f"DEBUG: Pobrano dane OCR: {parsed_ocr_data.get('items', [])}")

    # Przygotuj istniejące produkty z listy zakupów
    current_shopping_list_products = []
    for product in shopping_list.products:
        current_shopping_list_products.append({
            'name': product.name,
            'price': product.price,  # Już Decimal
            'assigned_friends': [f.id for f in product.assigned_friends_for_product],
            'paid_by': product.paid_by,  # Uwzględnij paid_by
            'db_id': product.id  # Oryginalne ID z bazy danych
        })
    print(f"DEBUG: Pobrano istniejące produkty z listy: {current_shopping_list_products}")

    try:
        # Wywołaj algorytm scalania
        merged_products_data = match_ocr_to_shopping_list(
            shopping_list_items=current_shopping_list_products,
            parsed_ocr_items=parsed_ocr_data["items"]
        )
        print(f"DEBUG: Wynik scalania z merging_services: {merged_products_data}")

        print(f"DEBUG: Usuwanie istniejących produktów i relacji dla listy ID: {shopping_list.id}")

        # 1. Najpierw znajdź wszystkie produkty z tej listy
        products_to_delete = Product.query.filter_by(shopping_list_id=shopping_list.id).all()
        product_ids_to_delete = [p.id for p in products_to_delete]

        # 2. Usuń relacje z product_friend_assignment dla tych produktów
        if product_ids_to_delete:
            from sqlalchemy import text
            # Tworzymy placeholder dla każdego ID
            placeholders = ','.join(['?' for _ in product_ids_to_delete])
            db.session.execute(
                text(f"DELETE FROM product_friend_assignment WHERE product_id IN ({placeholders})"),
                product_ids_to_delete
            )
            print(f"DEBUG: Usunięto relacje dla produktów: {product_ids_to_delete}")

        # 3. Teraz usuń produkty
        Product.query.filter_by(shopping_list_id=shopping_list.id).delete()
        db.session.commit()  # Zatwierdź usunięcie przed dodaniem nowych
        print(f"DEBUG: Istniejące produkty usunięte. Dodawanie scalonych produktów.")

        # 4. Opcjonalnie: wyczyść cache sesji SQLAlchemy
        db.session.expunge_all()

        for item_data in merged_products_data:
            price_decimal = None
            if isinstance(item_data['price'], Decimal):
                price_decimal = item_data['price']
            elif isinstance(item_data['price'], str) and item_data['price']:
                try:
                    price_decimal = Decimal(item_data['price'])
                except InvalidOperation:
                    print(
                        f"WARNING: Nie można przekonwertować ceny {item_data['price']} na Decimal dla {item_data['name']}. Ustawiam cenę na 0.00.")
                    price_decimal = Decimal('0.00')
            else:
                price_decimal = Decimal('0.00')

            new_product = Product(
                name=item_data['name'],
                price=price_decimal,
                shopping_list_id=shopping_list.id,
                paid_by=item_data.get('paid_by', current_user.id),
                # Zachowaj oryginalne paid_by lub ustaw na current_user
                is_purchased=False  # Zakładamy, że nowe/scalane elementy nie są jeszcze zakupione
            )

            # Add product to session and flush to get the ID
            db.session.add(new_product)
            db.session.flush()  # This assigns an ID to new_product

            # POPRAWKA: Bezpieczne przypisywanie znajomych z deduplikacją
            if 'assigned_friends' in item_data and item_data['assigned_friends']:
                # Ensure unique friend IDs and validate ownership
                unique_assigned_friends = set(item_data['assigned_friends'])
                print(f"DEBUG: Przypisywanie znajomych {unique_assigned_friends} do produktu {new_product.id}")

                for friend_id in unique_assigned_friends:
                    try:
                        # Validate that friend_id is valid and belongs to current_user
                        friend_obj = Friend.query.filter_by(
                            id=friend_id,
                            user_id=current_user.id
                        ).first()

                        if friend_obj:
                            # Sprawdź czy relacja już istnieje w bazie danych
                            from sqlalchemy import text
                            existing_assignment = db.session.execute(
                                text(
                                    "SELECT 1 FROM product_friend_assignment WHERE product_id = :product_id AND friend_id = :friend_id"),
                                {"product_id": new_product.id, "friend_id": friend_id}
                            ).fetchone()

                            if existing_assignment:
                                print(
                                    f"DEBUG: Relacja produkt {new_product.id} - znajomy {friend_id} już istnieje, pomijam")
                                continue

                            # Sprawdź też w sesji SQLAlchemy
                            if friend_obj not in new_product.assigned_friends_for_product:
                                new_product.assigned_friends_for_product.append(friend_obj)
                                print(f"DEBUG: Dodano znajomego {friend_id} do produktu {new_product.id}")
                            else:
                                print(
                                    f"DEBUG: Friend {friend_id} already assigned to product {new_product.id} in session")
                        else:
                            print(
                                f"WARNING: Friend ID {friend_id} not found or doesn't belong to user {current_user.id}")

                    except Exception as e:
                        print(
                            f"ERROR: Błąd podczas przypisywania znajomego {friend_id} do produktu {new_product.id}: {e}")
                        # Kontynuuj z następnym znajomym zamiast przerywać cały proces
                        continue

        # Commit all changes at once
        db.session.commit()
        flash(f'Produkty z paragonu zostały scalone z listą "{shopping_list.name}".', 'success')
        print(f"DEBUG: Scalanie zakończone sukcesem dla listy ID: {shopping_list.id}. Przekierowanie do edycji listy.")

        return redirect(url_for('receipt.edit_shopping_list', list_id=shopping_list.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Wystąpił błąd podczas scalania produktów: {e}', 'danger')
        print(f"ERROR: Błąd podczas scalania dla paragonu ID: {receipt_id}: {e}")
        return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

@receipt_bp.route('/receipt/delete/<int:receipt_id>', methods=['POST'])
@login_required
def delete_receipt(receipt_id):
    """
    Usuwa paragon z bazy danych i jego plik.
    """
    receipt = Receipt.query.get_or_404(receipt_id)
    if receipt.user_id != current_user.id:
        flash('Nie masz uprawnień do usunięcia tego paragonu.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        if receipt.file_path and os.path.exists(receipt.file_path):
            os.remove(receipt.file_path)
            print(f"Usunięto fizyczny plik paragonu: {receipt.file_path}")

        db.session.delete(receipt)
        db.session.commit()
        flash('Paragon został usunięty pomyślnie!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Błąd podczas usuwania paragonu: {e}', 'danger')

    if receipt.shopping_list_id:
        return redirect(url_for('receipt.edit_shopping_list', list_id=receipt.shopping_list_id))
    return redirect(url_for('main.dashboard'))


@receipt_bp.route('/receipt/export_csv/<int:receipt_id>', methods=['GET'])
@login_required
def export_receipt_csv(receipt_id):
    """
    Eksportuje przetworzone dane z paragonu do pliku CSV.
    """
    receipt = Receipt.query.get_or_404(receipt_id)
    if receipt.user_id != current_user.id:
        flash('Nie masz uprawnień do eksportowania danych z tego paragonu.', 'danger')
        return redirect(url_for('main.dashboard'))

    parsed_data = receipt.get_processed_data()
    if not parsed_data or "items" not in parsed_data:
        flash('Brak przetworzonych danych dla tego paragonu do eksportu.', 'warning')
        return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

    output = io.StringIO()
    writer = csv.writer(output)

    # Nagłówki CSV
    writer.writerow(["Nazwa Produktu", "Cena Całkowita", "Ilość", "Cena Jednostkowa", "Rabat"])

    # Wiersze CSV
    for item in parsed_data.get('items', []):
        name = item.get('name', '').replace('"', '""')  # Obsługa cudzysłowów w nazwach
        total_price = item.get('total_price', '0.00')
        quantity = item.get('quantity', '')
        unit_price = item.get('unit_price', '')
        discount_amount = item.get('discount_amount', '')
        writer.writerow([name, total_price, quantity, unit_price, discount_amount])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=paragon_{receipt.id}_export.csv"
    response.headers["Content-type"] = "text/csv"
    return response

