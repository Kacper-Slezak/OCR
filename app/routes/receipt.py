from flask import render_template, Blueprint, redirect, url_for, flash, request, current_app as app, send_file, \
    make_response, abort
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList, Product, Receipt, Friend, User
from app.services.ocr_services import process_receipt_image
from app.services.merging_services import match_ocr_to_shopping_list
from decimal import Decimal, InvalidOperation
import os
from werkzeug.utils import secure_filename
import io
import csv

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

        is_new_list = shopping_list is None

        if shopping_list:
            shopping_list.name = list_name
        else:
            shopping_list = ShoppingList(name=list_name, created_by=current_user.id)
            db.session.add(shopping_list)
            db.session.flush() # Potrzebne do uzyskania ID dla nowej listy przed dodaniem produktów

        # --- Zaktualizowana logika obsługi produktów ---
        # Pobierz bieżące produkty z bazy danych
        existing_products = {p.id: p for p in shopping_list.products} if shopping_list else {}
        products_to_keep_ids = set() # Zbiór ID produktów, które mają pozostać (zaktualizowane lub niezmienione)

        i = 0
        while f'products[{i}][name]' in request.form:
            product_id_str = request.form.get(f'products[{i}][db_id]', '').strip()
            product_name = request.form.get(f'products[{i}][name]', '').strip()
            product_price_str = request.form.get(f'products[{i}][price]', '').strip()
            assigned_friends_ids = request.form.getlist(f'products[{i}][assigned_friends][]')

            product_id = int(product_id_str) if product_id_str.isdigit() else None

            if product_name: # Przetwarzaj tylko produkty z nazwą
                product_price = Decimal('0.00')
                if product_price_str:
                    try:
                        product_price = Decimal(product_price_str.replace(',', '.'))
                    except InvalidOperation:
                        flash(f'Nieprawidłowy format ceny dla produktu "{product_name}". Użyto 0.00.', 'warning')
                        product_price = Decimal('0.00')

                # Sprawdź, czy to istniejący produkt do aktualizacji, czy nowy
                if product_id and product_id in existing_products:
                    # Aktualizuj istniejący produkt
                    product_obj = existing_products[product_id]
                    product_obj.name = product_name
                    product_obj.price = product_price

                    # Aktualizuj przypisanych znajomych
                    current_assigned_friends_ids = {f.id for f in product_obj.assigned_friends_for_product}
                    new_assigned_friends_ids_set = {int(fid) for fid in assigned_friends_ids if fid.isdigit()}

                    # Usuń znajomych, którzy zostali odznaczeni
                    for friend_id in current_assigned_friends_ids - new_assigned_friends_ids_set:
                        friend_to_remove = Friend.query.get(friend_id)
                        if friend_to_remove: # Upewnij się, że znajomy istnieje
                            product_obj.assigned_friends_for_product.remove(friend_to_remove)

                    # Dodaj nowych znajomych, którzy zostali zaznaczeni
                    for friend_id in new_assigned_friends_ids_set - current_assigned_friends_ids:
                        friend_to_add = Friend.query.get(friend_id)
                        if friend_to_add and friend_to_add.user_id == current_user.id: # Sprawdź własność znajomego
                            product_obj.assigned_friends_for_product.append(friend_to_add)

                    products_to_keep_ids.add(product_id) # Oznacz, że ten produkt ma pozostać
                else:
                    # Dodaj nowy produkt
                    new_product = Product(
                        name=product_name,
                        price=product_price,
                        shopping_list_id=shopping_list.id,
                        paid_by=current_user.id, # Zakładamy, że aktualny użytkownik płaci
                        is_purchased=False
                    )
                    db.session.add(new_product)
                    db.session.flush() # Flush, aby uzyskać ID dla nowego produktu przed przypisaniem znajomych

                    # Przypisz znajomych do nowego produktu
                    for friend_id in [int(fid) for fid in assigned_friends_ids if fid.isdigit()]:
                        friend = Friend.query.get(friend_id)
                        if friend and friend.user_id == current_user.id:
                            new_product.assigned_friends_for_product.append(friend)
            i += 1

        # Usuń produkty, które były w bazie danych, ale nie zostały przesłane w formularzu
        # (czyli te, które użytkownik usunął w UI)
        for product_id, product_obj in existing_products.items():
            if product_id not in products_to_keep_ids:
                db.session.delete(product_obj)
        # --- Koniec zaktualizowanej logiki obsługi produktów ---

        try:
            db.session.commit()

            if is_new_list:
                flash('Lista zakupów została pomyślnie utworzona! Teraz możesz wgrać paragon.', 'success')
            else:
                flash('Lista zakupów została pomyślnie zaktualizowana!', 'success')

            return redirect(url_for('receipt.edit_shopping_list', list_id=shopping_list.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Błąd podczas zapisywania listy zakupów: {e}', 'danger')
            app.logger.exception("Błąd podczas zapisywania listy zakupów") # Dodaj logowanie błędu
            return redirect(request.url)

    # Żądanie GET: Wyświetl formularz
    products_data = []
    if shopping_list:
        for product in shopping_list.products:
            products_data.append({
                'name': product.name,
                'price': product.price,
                'assigned_friends': [f.id for f in product.assigned_friends_for_product],
                'db_id': product.id # Przekazujemy ID produktu do JS
            })

    all_friends_for_user = current_user.friends_owned.all()
    all_friends_for_js = [{'id': friend.id, 'name': friend.name} for friend in all_friends_for_user]

    return render_template(
        'recipt/edit_shopping_list.html',
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
        return redirect(url_for('main.dashboard'))
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
    if shopping_list.created_by != current_user.id:
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
            shopping_list_id=list_id,
            status='Uploaded'
        )
        db.session.add(new_receipt)
        db.session.commit()

        flash('Paragon został wgrany i jest przetwarzany.', 'info')

        process_receipt_image(new_receipt.id, file_path)

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

            if name:
                price_decimal = Decimal('0.00')
                if total_price_str:
                    try:
                        price_decimal = Decimal(total_price_str.replace(',', '.'))
                    except InvalidOperation:
                        flash(f'Nieprawidłowy format ceny dla pozycji OCR "{name}". Użyto 0.00.', 'warning')
                        price_decimal = Decimal('0.00')

                corrected_ocr_items.append(
                    {'name': name, 'total_price': str(price_decimal)})
            i += 1

        parsed_ocr_data['items'] = corrected_ocr_items
        receipt.set_processed_data(parsed_ocr_data)
        db.session.commit()
        flash('Korekty OCR zapisane.', 'success')

        return redirect(url_for('receipt.merge_ocr_with_list', receipt_id=receipt.id))

    return render_template(
        'ocr/review_ocr_results.html',
        receipt=receipt,
        ocr_items=parsed_ocr_data.get('items', [])
    )


@receipt_bp.route('/receipt/merge/<int:receipt_id>', methods=['GET'])
@login_required
def merge_ocr_with_list(receipt_id):
    """
    Scala dane z paragonu (po OCR) z produktami na powiązanej liście zakupów.
    """
    app.logger.info(f"DEBUG: Rozpoczynanie scalania dla paragonu ID: {receipt_id}")
    receipt = Receipt.query.get_or_404(receipt_id)
    if receipt.user_id != current_user.id:
        flash('Nie masz uprawnień do scalania danych z tego paragonu.', 'danger')
        app.logger.warning(f"DEBUG: Błąd uprawnień dla paragonu ID: {receipt_id}. Użytkownik {current_user.id} nie jest właścicielem.")
        return redirect(url_for('main.dashboard'))

    if not receipt.shopping_list_id:
        flash('Ten paragon nie jest powiązany z żadną listą zakupów. Najpierw go powiąż.', 'warning')
        app.logger.warning(f"DEBUG: Paragon ID: {receipt_id} nie jest powiązany z listą zakupów.")
        return redirect(url_for('main.dashboard'))

    shopping_list = ShoppingList.query.get_or_404(receipt.shopping_list_id)
    if shopping_list.created_by != current_user.id and current_user not in shopping_list.participants.all():
        flash('Nie masz uprawnień do modyfikowania tej listy zakupów.', 'danger')
        app.logger.warning(f"DEBUG: Błąd uprawnień dla listy zakupów ID: {shopping_list.id}. Użytkownik {current_user.id} nie jest twórcą ani uczestnikiem.")
        return redirect(url_for('main.dashboard'))

    parsed_ocr_data = receipt.get_processed_data()
    if not parsed_ocr_data or "items" not in parsed_ocr_data:
        flash('Brak przetworzonych danych OCR do scalenia.', 'warning')
        app.logger.warning(f"DEBUG: Brak przetworzonych danych OCR dla paragonu ID: {receipt_id}.")
        return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

    app.logger.debug(f"DEBUG: Pobrano dane OCR: {parsed_ocr_data.get('items', [])}")

    current_shopping_list_products = []
    for product in shopping_list.products:
        current_shopping_list_products.append({
            'name': product.name,
            'price': product.price,
            'assigned_friends': [f.id for f in product.assigned_friends_for_product],
            'paid_by': product.paid_by,
            'db_id': product.id
        })
    app.logger.debug(f"DEBUG: Pobrano istniejące produkty z listy: {current_shopping_list_products}")

    try:
        merged_products_data = match_ocr_to_shopping_list(
            shopping_list_items=current_shopping_list_products,
            parsed_ocr_items=parsed_ocr_data["items"]
        )
        app.logger.debug(f"DEBUG: Wynik scalania z merging_services: {merged_products_data}")

        # Usuń wszystkie obecne produkty i dodaj nowe, scalone.
        # WAŻNE: Tutaj dokonujemy usunięcia i ponownego dodania WSZYSTKICH produktów
        # po scaleniu z OCR. Jeśli chcesz zachować istniejące i tylko dodawać nowe/aktualizować,
        # potrzebna jest podobna logika jak w edit_shopping_list.
        app.logger.info(f"DEBUG: Usuwanie istniejących produktów dla listy ID: {shopping_list.id} przed scaleniem.")
        Product.query.filter_by(shopping_list_id=shopping_list.id).delete()
        db.session.commit()
        app.logger.info(f"DEBUG: Istniejące produkty usunięte. Dodawanie scalonych produktów.")

        for item_data in merged_products_data:
            price_decimal = Decimal('0.00')
            if isinstance(item_data['price'], Decimal):
                price_decimal = item_data['price']
            elif isinstance(item_data['price'], str) and item_data['price']:
                try:
                    price_decimal = Decimal(item_data['price'])
                except InvalidOperation:
                    app.logger.warning(f"WARNING: Nie można przekonwertować ceny {item_data['price']} na Decimal dla {item_data['name']}. Ustawiam cenę na 0.00.")
                    price_decimal = Decimal('0.00')

            new_product = Product(
                name=item_data['name'],
                price=price_decimal,
                shopping_list_id=shopping_list.id,
                paid_by=item_data.get('paid_by', current_user.id),
                is_purchased=False
            )
            db.session.add(new_product)
            db.session.flush() # Flush aby uzyskać ID dla nowego produktu

            if 'assigned_friends' in item_data and item_data['assigned_friends']:
                for friend_id in item_data['assigned_friends']:
                    friend_obj = Friend.query.get(friend_id)
                    if friend_obj and friend_obj.user_id == current_user.id:
                        new_product.assigned_friends_for_product.append(friend_obj)

        db.session.commit()
        flash(f'Produkty z paragonu zostały scalone z listą "{shopping_list.name}".', 'success')
        app.logger.info(f"DEBUG: Scalanie zakończone sukcesem dla listy ID: {shopping_list.id}. Przekierowanie do edycji listy.")
        return redirect(url_for('receipt.edit_shopping_list', list_id=shopping_list.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Wystąpił błąd podczas scalania produktów: {e}', 'danger')
        app.logger.exception(f"ERROR: Błąd podczas scalania dla paragonu ID: {receipt_id}")
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
            app.logger.info(f"Usunięto fizyczny plik paragonu: {receipt.file_path}")

        db.session.delete(receipt)
        db.session.commit()
        flash('Paragon został usunięty pomyślnie!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Błąd podczas usuwania paragonu: {e}', 'danger')
        app.logger.exception(f"Błąd podczas usuwania paragonu ID: {receipt_id}")

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

    writer.writerow(["Nazwa Produktu", "Cena Całkowita", "Ilość", "Cena Jednostkowa", "Rabat"])

    for item in parsed_data.get('items', []):
        name = item.get('name', '').replace('"', '""')
        total_price = item.get('total_price', '0.00')
        quantity = item.get('quantity', '')
        unit_price = item.get('unit_price', '')
        discount_amount = item.get('discount_amount', '')
        writer.writerow([name, total_price, quantity, unit_price, discount_amount])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=paragon_{receipt.id}_export.csv"
    response.headers["Content-type"] = "text/csv"
    return response