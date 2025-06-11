# app/routes/ocr.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

# Importujemy obiekt bazy danych i model Receipt
from app import db
from app.models import Receipt

# Importujemy funkcję z Twojego serwisu OCR
from app.services.ocr_service import process_receipt_image

# Tworzymy Blueprint dla funkcjonalności OCR
# `bp` to nasz "niebieski plan", który będzie zawierał wszystkie trasy związane z OCR.
# `url_prefix='/ocr'` oznacza, że wszystkie trasy w tym Blueprint będą poprzedzone '/ocr'.
# Np. `/upload` stanie się `/ocr/upload`.
bp = Blueprint('ocr', __name__, url_prefix='/ocr')

# --- Funkcje pomocnicze ---

def allowed_file(filename):
    """
    Sprawdza, czy rozszerzenie pliku jest dozwolone.
    Dozwolone rozszerzenia są zdefiniowane w config.py.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# --- Trasy (Routes) ---

@bp.route('/upload', methods=['GET', 'POST'])
@login_required # Ta dekorator wymaga, aby użytkownik był zalogowany, aby uzyskać dostęp do tej trasy.
def upload_receipt():
    """
    Obsługuje przesyłanie plików paragonów.
    Metoda GET: Wyświetla formularz do przesyłania.
    Metoda POST: Przetwarza przesłany plik.
    """
    if request.method == 'POST':
        # 1. Sprawdź, czy w żądaniu POST znajduje się część z plikiem
        if 'file' not in request.files:
            flash('Brak części pliku w żądaniu.', 'error') # Wiadomość flash dla użytkownika
            return redirect(request.url) # Przekieruj z powrotem do formularza

        file = request.files['file']

        # 2. Sprawdź, czy użytkownik faktycznie wybrał plik
        if file.filename == '':
            flash('Nie wybrano pliku.', 'error')
            return redirect(request.url)

        # 3. Walidacja pliku (czy istnieje i ma dozwolone rozszerzenie)
        if file and allowed_file(file.filename):
            # Zabezpiecz nazwę pliku, aby uniknąć problemów bezpieczeństwa (np. path traversal)
            filename = secure_filename(file.filename)
            # Pobierz folder do uploadu z konfiguracji aplikacji
            upload_folder = current_app.config['UPLOAD_FOLDER']

            # Upewnij się, że folder do zapisu plików istnieje
            os.makedirs(upload_folder, exist_ok=True)

            # Pełna ścieżka do zapisanego pliku
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path) # Zapisz plik na serwerze

            # 4. Utwórz nowy wpis paragonu w bazie danych
            new_receipt = Receipt(
                user_id=current_user.id, # Powiąż paragon z aktualnie zalogowanym użytkownikiem
                file_path=file_path,     # Zapisz ścieżkę do pliku w bazie
                status='uploaded'        # Ustaw początkowy status
            )
            db.session.add(new_receipt)
            db.session.commit() # Zatwierdź dodanie nowego paragonu do bazy

            # 5. Deleguj zadanie przetwarzania OCR do serwisu
            # print(f"DEBUG: Przekazuję do serwisu OCR: ID={new_receipt.id}, Ścieżka={file_path}")
            try:
                # W przyszłości, dla dużych plików lub długich procesów,
                # to wywołanie powinno być asynchroniczne (np. z Celery/APScheduler).
                # Na razie jest synchroniczne dla prostoty.
                process_receipt_image(new_receipt.id, file_path)
                flash('Paragon przesłany i przetwarzanie OCR rozpoczęte!', 'success')
            except Exception as e:
                # Obsługa błędów, jeśli coś pójdzie nie tak podczas uruchamiania serwisu OCR
                print(f"Błąd podczas uruchamiania serwisu OCR dla paragonu {new_receipt.id}: {e}")
                flash(f'Wystąpił błąd podczas przetwarzania paragonu: {e}', 'error')
                # Możesz zmienić status paragonu na 'error' tutaj, jeśli chcesz
                # (chociaż serwis też to robi)
                new_receipt.status = 'error_upload_stage' # Specjalny status
                db.session.commit()

            # Przekieruj użytkownika na listę paragonów, aby mógł zobaczyć status
            return redirect(url_for('ocr.list_receipts'))
        else:
            # Walidacja nie powiodła się (np. niewłaściwy typ pliku)
            flash('Dozwolone typy plików to: png, jpg, jpeg, gif.', 'error')
            return redirect(request.url)

    # Dla żądania GET, po prostu renderuj formularz przesyłania paragonu
    return render_template('ocr/upload_receipt.html')


@bp.route('/list')
@login_required
def list_receipts():
    """
    Wyświetla listę wszystkich paragonów przesłanych przez bieżącego użytkownika.
    """
    # Pobierz paragony tylko aktualnie zalogowanego użytkownika, posortowane od najnowszych
    receipts = Receipt.query.filter_by(user_id=current_user.id).order_by(Receipt.upload_date.desc()).all()
    return render_template('ocr/list_receipts.html', receipts=receipts)


@bp.route('/<int:receipt_id>')
@login_required
def view_receipt(receipt_id):
    """
    Wyświetla szczegółowe informacje o pojedynczym paragonie, w tym surowy tekst i sparsowane dane.
    Użytkownik może zobaczyć tylko swoje paragony.
    """
    # Pobierz paragon po ID, ale upewnij się, że należy do aktualnie zalogowanego użytkownika.
    # `.first_or_404()` automatycznie zwraca błąd 404, jeśli paragon nie istnieje lub nie należy do użytkownika.
    receipt = Receipt.query.filter_by(id=receipt_id, user_id=current_user.id).first_or_404()

    # Parsowane dane są przechowywane jako string JSON.
    # Metoda `get_processed_data()` w modelu Receipt (powinieneś ją mieć)
    # powinna konwertować ten string z powrotem na słownik Pythona.
    parsed_data = receipt.get_processed_data()

    return render_template('ocr/view_receipt.html', receipt=receipt, parsed_data=parsed_data)

# Dodatkowa trasa dla podglądu pliku (może być używana w przyszłości)
# @bp.route('/view_file/<filename>')
# @login_required
# def view_file(filename):
#     # Ogranicz dostęp, aby użytkownik mógł widzieć tylko swoje pliki,
#     # które są powiązane z paragonami. To wymaga bardziej zaawansowanej logiki.
#     # Na razie pliki są dostępne przez static/uploads
#     return redirect(url_for('static', filename='uploads/' + secure_filename(filename)))