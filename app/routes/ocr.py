# app/routes/ocr.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

from app import db
from app.models import Receipt

# Importujemy funkcje z Twojego serwisu OCR
from app.services.ocr_services import process_receipt_image

bp = Blueprint('ocr', __name__, url_prefix='/ocr')


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_receipt():
    if request.method == 'POST':
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
                user_id=current_user.id,  # Używa ID zalogowanego użytkownika
                file_path=file_path,
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

            return redirect(url_for('ocr.list_receipts'))
        else:
            flash('Dozwolone typy plików to: png, jpg, jpeg, gif.', 'error')
            return redirect(request.url)

    return render_template('ocr/upload_receipt.html')


@bp.route('/list')
@login_required
def list_receipts():
    receipts = Receipt.query.filter_by(user_id=current_user.id).order_by(Receipt.upload_date.desc()).all()
    return render_template('ocr/list_receipts.html', receipts=receipts)


@bp.route('/<int:receipt_id>')
@login_required
def view_receipt(receipt_id):
    receipt = Receipt.query.filter_by(id=receipt_id, user_id=current_user.id).first_or_404()
    parsed_data = receipt.get_processed_data()
    return render_template('ocr/view_receipt.html', receipt=receipt, parsed_data=parsed_data)


@bp.route('/receipt/<int:receipt_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_receipt(receipt_id):
    receipt = Receipt.query.filter_by(id=receipt_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        edited_data = []
        i = 0
        while True:
            name = request.form.get(f'product_name_{i}')
            price_str = request.form.get(f'product_price_{i}')  # Pobierz jako string

            if name is None and price_str is None:
                break

            if name and price_str:
                try:
                    price = float(price_str.replace(',', '.'))  # Konwersja na float, obsługa przecinka
                    edited_data.append({'name': name, 'price': price})
                except ValueError:
                    flash(f"Nieprawidłowy format ceny dla '{name}'. Użyj liczby z kropką lub przecinkiem.", 'danger')
                    # W przypadku błędu formatu, ponownie renderuj formularz z danymi, które użytkownik wprowadził
                    # aby nie stracił pracy. To wymagałoby złożenia nowej listy produktów z request.form.
                    # Dla uproszczenia, na razie przekierowujemy:
                    return redirect(url_for('ocr.edit_receipt', receipt_id=receipt.id))
            i += 1

        receipt.set_processed_data(edited_data)
        receipt.status = 'processed'  # Lub 'corrected'
        db.session.commit()
        flash('Paragon został pomyślnie skorygowany!', 'success')
        return redirect(url_for('ocr.list_receipts'))
    else:
        processed_products = receipt.get_processed_data()
        if not processed_products:
            # Jeśli nie ma przetworzonych danych, możesz zainicjować pustą listę do edycji.
            processed_products = []
            flash('Brak przetworzonych danych dla tego paragonu. Rozpocznij edycję od zera.', 'info')

        return render_template('ocr/edit_receipt.html', receipt=receipt, processed_products=processed_products)


@bp.route('/receipt/<int:receipt_id>/delete', methods=['POST'])
@login_required
def delete_receipt(receipt_id):
    # Pobiera paragon, ale TYLKO jeśli należy do aktualnie zalogowanego użytkownika
    receipt = Receipt.query.filter_by(id=receipt_id, user_id=current_user.id).first_or_404()

    if os.path.exists(receipt.file_path):
        try:
            os.remove(receipt.file_path)
            print(f"Usunięto plik: {receipt.file_path}")
        except OSError as e:
            print(f"Błąd podczas usuwania pliku {receipt.file_path}: {e}")
            flash(f"Błąd podczas usuwania pliku paragonu: {e}", "warning")

    db.session.delete(receipt)
    db.session.commit()
    flash('Paragon został usunięty!', 'success')
    return redirect(url_for('ocr.list_receipts'))


@bp.route('/view_image/<filename>')
@login_required
def view_image(filename):
    filename_secured = secure_filename(filename)

    receipt = Receipt.query.filter(
        Receipt.user_id == current_user.id,
        Receipt.file_path.ilike(f'%{filename_secured}')
    ).first()

    if receipt is None:
        abort(404)

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename_secured)
