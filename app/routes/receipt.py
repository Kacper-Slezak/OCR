from flask import render_template, Blueprint, redirect, url_for, flash, request, current_app as app, \
    make_response
from flask_login import login_required, current_user
from app import db
from app.models import ShoppingList, Product, Receipt, Friend
from app.services.ocr_services import process_receipt_image
from app.services.merging_services import match_ocr_to_shopping_list
from decimal import Decimal, InvalidOperation
import os
from werkzeug.utils import secure_filename
import io
import csv

receipt_bp = Blueprint('receipt', __name__)


def safe_assign_friends_to_product(product, friend_ids, current_user_id):
    """
    Bezpiecznie przypisuje znajomych do produktu, unikając duplikatów.
    """
    if not friend_ids:
        return

    # Deduplikacja
    unique_friend_ids = list(set(friend_ids))

    for friend_id in unique_friend_ids:
        try:
            friend = Friend.query.filter_by(
                id=friend_id,
                user_id=current_user_id
            ).first()

            if friend and friend not in product.assigned_friends_for_product:
                product.assigned_friends_for_product.append(friend)
                print(f"DEBUG: Przypisano znajomego {friend_id} do produktu {product.id}")

        except Exception as e:
            print(f"Błąd przypisywania znajomego {friend_id}: {e}")
            continue



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


        products_data = []
        i = 0
        while f'products[{i}][name]' in request.form:
            product_name = request.form.get(f'products[{i}][name]', '').strip()
            product_price_str = request.form.get(f'products[{i}][price]', '').strip()
            assigned_friends_ids = request.form.getlist(f'products[{i}][assigned_friends][]')

            if product_name:
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

        # Usuwamy istniejące produkty dla tej listy przed dodaniem nowych z formularza
        if shopping_list.id:
            try:
                products_to_delete = Product.query.filter_by(shopping_list_id=shopping_list.id).all()
                for product in products_to_delete:
                    product.assigned_friends_for_product.clear()

                db.session.flush()  # Zatwierdzamy czyszczenie relacji
                Product.query.filter_by(shopping_list_id=shopping_list.id).delete()
                db.session.flush()

            except Exception as e:
                print(f"Błąd podczas usuwania produktów: {e}")
                db.session.rollback()
                flash(f'Błąd podczas aktualizacji listy: {e}', 'danger')
                return redirect(request.url)


        for p_data in products_data:
            new_product = Product(
                name=p_data['name'],
                price=p_data['price'],
                shopping_list_id=shopping_list.id,
                paid_by=current_user.id,
                is_purchased=False
            )
            db.session.add(new_product)
            db.session.flush()  # Potrzebne do uzyskania ID produktu przed przypisaniem znajomych

            safe_assign_friends_to_product(new_product, p_data['assigned_friends_ids'], current_user.id)

        try:
            db.session.commit()
            flash('Lista zakupów została pomyślnie zapisana!', 'success')
            return redirect(url_for('receipt.edit_shopping_list', list_id=shopping_list.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Błąd podczas zapisywania listy zakupów: {e}', 'danger')
            return redirect(request.url)


    products_data = []
    if shopping_list:
        for product in shopping_list.products:
            products_data.append({
                'name': product.name,
                'price': product.price,
                'assigned_friends': [f.id for f in product.assigned_friends_for_product],
                'paid_by': product.paid_by,
                'db_id': product.id
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
    except Exception as e:
        db.session.rollback()
        flash(f'Błąd podczas usuwania listy zakupów: {e}', 'danger')

    return redirect(url_for('main.dashboard'))



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
            shopping_list_id=list_id,  # Powiązujemy paragon z listą zakupów
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

        # Zapisujemy skorygowane dane z powrotem do receipt.processed_data
        parsed_ocr_data['items'] = corrected_ocr_items
        receipt.set_processed_data(parsed_ocr_data)
        db.session.commit()
        flash('Korekty OCR zapisane.', 'success')

        # Przechodzimy do scalania z listą zakupów
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
    POPRAWIONA WERSJA z lepszą obsługą błędów i transakcji.
    """
    print(f"DEBUG: Rozpoczynanie scalania dla paragonu ID: {receipt_id}")

    receipt = Receipt.query.get_or_404(receipt_id)
    if receipt.user_id != current_user.id:
        flash('Nie masz uprawnień do scalania danych z tego paragonu.', 'danger')
        return redirect(url_for('main.dashboard'))

    if not receipt.shopping_list_id:
        flash('Ten paragon nie jest powiązany z żadną listą zakupów.', 'warning')
        return redirect(url_for('main.dashboard'))

    shopping_list = ShoppingList.query.get_or_404(receipt.shopping_list_id)
    if shopping_list.created_by != current_user.id and current_user not in shopping_list.participants.all():
        flash('Nie masz uprawnień do modyfikowania tej listy zakupów.', 'danger')
        return redirect(url_for('main.dashboard'))

    parsed_ocr_data = receipt.get_processed_data()
    if not parsed_ocr_data or "items" not in parsed_ocr_data or not parsed_ocr_data["items"]:
        flash('Brak przetworzonych danych OCR do scalenia.', 'warning')
        return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

    print(f"DEBUG: Pobrano {len(parsed_ocr_data['items'])} elementów z OCR")

    current_shopping_list_products = []
    for product in shopping_list.products:
        current_shopping_list_products.append({
            'name': product.name,
            'price': product.price,
            'assigned_friends': [f.id for f in product.assigned_friends_for_product],
            'paid_by': product.paid_by,
            'db_id': product.id
        })

    print(f"DEBUG: Pobrano {len(current_shopping_list_products)} istniejących produktów")

    try:
        # Wywołujemy algorytm scalania
        merged_products_data = match_ocr_to_shopping_list(
            shopping_list_items=current_shopping_list_products,
            parsed_ocr_items=parsed_ocr_data["items"]
        )

        # SPRAWDZENIE WYNIKÓW SCALANIA
        if not merged_products_data:
            flash('Algorytm scalania nie zwrócił żadnych produktów.', 'warning')
            return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

        if not isinstance(merged_products_data, list):
            flash('Algorytm scalania zwrócił nieprawidłowy format danych.', 'error')
            return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

        print(f"DEBUG: Algorytm scalania zwrócił {len(merged_products_data)} produktów")

        # BEZPIECZNE USUWANIE STARYCH PRODUKTÓW
        success = _safely_clear_shopping_list_products(shopping_list.id)
        if not success:
            flash('Błąd podczas usuwania starych produktów.', 'danger')
            return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

        # DODAWANIE NOWYCH PRODUKTÓW
        success = _safely_add_merged_products(merged_products_data, shopping_list.id, current_user.id)
        if not success:
            flash('Błąd podczas dodawania nowych produktów.', 'danger')
            return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))

        flash(f'Produkty z paragonu zostały scalone z listą "{shopping_list.name}".', 'success')
        return redirect(url_for('receipt.edit_shopping_list', list_id=shopping_list.id))

    except Exception as e:
        print(f"ERROR: Błąd podczas scalania: {e}")
        db.session.rollback()
        flash(f'Wystąpił nieoczekiwany błąd podczas scalania: {str(e)}', 'danger')
        return redirect(url_for('receipt.review_ocr_results', receipt_id=receipt.id))


def _safely_clear_shopping_list_products(shopping_list_id):
    """
    Bezpiecznie usuwa wszystkie produkty z listy zakupów.
    Zwraca True jeśli sukces, False jeśli błąd.
    """
    try:
        print(f"DEBUG: Rozpoczynanie usuwania produktów dla listy {shopping_list_id}")

        products_to_delete = Product.query.filter_by(shopping_list_id=shopping_list_id).all()
        print(f"DEBUG: Znaleziono {len(products_to_delete)} produktów do usunięcia")

        if not products_to_delete:
            print("DEBUG: Brak produktów do usunięcia")
            return True

        # Czyścimy relacje many-to-many dla każdego produktu
        for product in products_to_delete:
            try:
                # Sprawdzamy czy produkt ma relacje
                friends_count = len(product.assigned_friends_for_product)
                print(f"DEBUG: Produkt {product.id} ma {friends_count} przypisanych znajomych")

                # Czyścimy relacje
                product.assigned_friends_for_product.clear()

            except Exception as e:
                print(f"ERROR: Błąd czyszczenia relacji dla produktu {product.id}: {e}")
                db.session.rollback()
                return False

        db.session.flush()
        print("DEBUG: Relacje wyczyszczone")

        deleted_count = Product.query.filter_by(shopping_list_id=shopping_list_id).delete()
        print(f"DEBUG: Usunięto {deleted_count} produktów")

        db.session.commit()
        print("DEBUG: Usuwanie produktów zakończone sukcesem")
        return True

    except Exception as e:
        print(f"ERROR: Błąd podczas usuwania produktów: {e}")
        db.session.rollback()
        return False


def _safely_add_merged_products(merged_products_data, shopping_list_id, current_user_id):
    """
    Bezpiecznie dodaje scalone produkty do listy zakupów.
    Zwraca True jeśli sukces, False jeśli błąd.
    """
    try:
        print(f"DEBUG: Rozpoczynanie dodawania {len(merged_products_data)} produktów")

        for i, item_data in enumerate(merged_products_data):
            print(f"DEBUG: Przetwarzanie produktu {i + 1}: {item_data}")

            if not isinstance(item_data, dict):
                print(f"ERROR: Produkt {i + 1} nie jest słownikiem: {type(item_data)}")
                continue

            if 'name' not in item_data or not item_data['name']:
                print(f"ERROR: Produkt {i + 1} nie ma nazwy")
                continue

            price_decimal = _convert_price_to_decimal(item_data.get('price', '0.00'))

            new_product = Product(
                name=str(item_data['name']).strip(),
                price=price_decimal,
                shopping_list_id=shopping_list_id,
                paid_by=item_data.get('paid_by', current_user_id),
                is_purchased=False
            )

            db.session.add(new_product)
            db.session.flush()

            print(f"DEBUG: Utworzono produkt {new_product.id}: {new_product.name}")

            assigned_friends = item_data.get('assigned_friends', [])
            if assigned_friends:
                success = _assign_friends_to_product(new_product, assigned_friends, current_user_id)
                if not success:
                    print(f"WARNING: Błąd przypisywania znajomych do produktu {new_product.id}")

        db.session.commit()
        print("DEBUG: Dodawanie produktów zakończone sukcesem")
        return True

    except Exception as e:
        print(f"ERROR: Błąd podczas dodawania produktów: {e}")
        db.session.rollback()
        return False


def _convert_price_to_decimal(price_value):
    """
    Bezpiecznie konwertuje cenę na Decimal.
    """
    if isinstance(price_value, Decimal):
        return price_value

    if price_value is None:
        return Decimal('0.00')

    try:
        price_str = str(price_value).replace(',', '.').strip()
        if not price_str:
            return Decimal('0.00')
        return Decimal(price_str)
    except (InvalidOperation, ValueError) as e:
        print(f"WARNING: Nie można przekonwertować ceny '{price_value}' na Decimal: {e}")
        return Decimal('0.00')


def _assign_friends_to_product(product, friend_ids, current_user_id):
    """
    Bezpiecznie przypisuje znajomych do produktu.
    """
    try:
        if not friend_ids:
            return True

        # Walidacja i deduplikacja
        valid_friend_ids = []
        for friend_id in friend_ids:
            try:
                friend_id_int = int(friend_id)
                if friend_id_int not in valid_friend_ids:
                    valid_friend_ids.append(friend_id_int)
            except (ValueError, TypeError):
                print(f"WARNING: Nieprawidłowe ID znajomego: {friend_id}")
                continue

        # Przypisywanie znajomych
        for friend_id in valid_friend_ids:
            friend = Friend.query.filter_by(
                id=friend_id,
                user_id=current_user_id
            ).first()

            if friend:
                # Sprawdzamy czy znajomy nie jest już przypisany
                if friend not in product.assigned_friends_for_product:
                    product.assigned_friends_for_product.append(friend)
                    print(f"DEBUG: Przypisano znajomego {friend_id} do produktu {product.id}")
                else:
                    print(f"DEBUG: Znajomy {friend_id} już przypisany do produktu {product.id}")
            else:
                print(f"WARNING: Nie znaleziono znajomego o ID {friend_id} dla użytkownika {current_user_id}")

        return True

    except Exception as e:
        print(f"ERROR: Błąd przypisywania znajomych: {e}")
        return False


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
