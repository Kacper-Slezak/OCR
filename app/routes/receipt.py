import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
# Zmień Receipt na ShoppingList, jeśli to ten model przechowuje listy zakupów
from app.models import ShoppingList, Friend, Product # <--- WAŻNE: Dodaj Friend i Product
from app.services.ocr_services import process_receipt_image


receipt_bp = Blueprint('receipt', __name__, url_prefix='/lists_edition')

@receipt_bp.route('/', methods=['GET'])
@receipt_bp.route('/<int:list_id>', methods=['GET'])
@login_required
def lists_edition(list_id=None):
    shopping_list_data = [] # Dane produktów do przekazania do JS
    list_name = "" # Domyślna pusta nazwa

    if list_id:
        # Próba załadowania konkretnej listy po ID
        # Zmień Receipt na ShoppingList
        current_list = ShoppingList.query.filter_by(id=list_id, created_by=current_user.id).first() # Zmień user_id na created_by
        if current_list:
            list_name = current_list.name
            # Przygotuj dane produktów dla JavaScriptu
            # Zakładamy, że lista.products jest relacją do Product
            for product in current_list.products:
                # Upewnij się, że masz relację assigned_friends_for_product na modelu Product
                assigned_friends_ids = [friend.id for friend in product.assigned_friends_for_product]
                shopping_list_data.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price), # Przekształć Decimal na float dla JSON
                    'assigned_friends': assigned_friends_ids
                })
        else:
            flash('Lista zakupów o podanym ID nie została znaleziona lub nie masz do niej dostępu.', 'danger')
            return redirect(url_for('main.dashboard')) # <--- WAŻNE: Przekierowanie na główny dashboard

    # Przygotuj dane znajomych z bazy danych, a nie mock
    all_friends_data = [{'id': friend.id, 'name': friend.name} for friend in
                        current_user.friends_owned.all()]  # <--- WAŻNE: Pobieraj z bazy danych

    return render_template(
        'recipt/lists_edition.html',  # <--- WAŻNE: Poprawiona nazwa szablonu na taką, którą używaliśmy wcześniej
        shopping_list_items=json.dumps(shopping_list_data),
        all_friends=json.dumps(all_friends_data),
        list_id=list_id,
        list_name=list_name  # Przekaż nazwę listy do szablonu
    )
# pewnie do wywalenia, latwiej pewnie doadaptowac to co jest juz w ocrze
@receipt_bp.route('/upload', methods=['POST'])
@login_required
def upload_receipt(receipt_id):
    list_id = request.form.get('list_id')
    if 'file' not in request.files:
        flash('Brak części pliku w żądaniu.', 'error')
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        flash('Nie wybrano pliku.', 'error')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        new_receipt = Receipt(
            id=receipt_id,
            user_id=current_user.id,
            file_path=file_path,
            shopping_list_id=list_id,
            status='uploaded'
        )
        db.session.add(new_receipt)
        db.session.commit()

        try:
            process_receipt_image(new_receipt.id, file_path)
            flash('Paragon przesłany i przetwarzanie OCR rozpoczęte!', 'success')
        except Exception as e:
            print(f"Błąd podczas uruchamiania serwisu OCR dla paragonu {new_receipt.id}: {e}")
            flash(f'Wystąpił błąd podczas przetwarzania paragonu: {e}', 'error')
            db.session.rollback()
            new_receipt.status = 'error_during_processing_init'
            db.session.commit()

    return redirect(url_for('ocr.edit_receipt', receipt_id=new_receipt.id))

# Usunięcie całej funkcji save_shopping_list, ponieważ jej logika została przeniesiona do main.py
# @receipt_bp.route('/save', methods=['POST'])
# @login_required
# def save_shopping_list():
#    ... ta funkcja jest USUNIĘTA ...

# Możesz zostawić endpoint do usuwania listy, jeśli chcesz.
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