# app/routes/ocr.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

# Importujemy obiekt bazy danych i model Receipt
from app import db
from app.models import Receipt

# `bp` to nasz "niebieski plan", który będzie zawierał wszystkie trasy związane z OCR.
# Importujemy funkcję z Twojego serwisu OCR
from app.services.ocr_services import process_receipt_image

# Tworzymy Blueprint dla funkcjonalności OCR
# `url_prefix='/ocr'` oznacza, że wszystkie trasy w tym Blueprint będą poprzedzone '/ocr'.
# Np. `/upload` stanie się `/ocr/upload`.
bp = Blueprint('ocr', __name__, url_prefix='/ocr')

# --- Funkcje pomocnicze ---

def allowed_file(filename):
    """
    Sprawdza, czy rozszerzenie pliku jest dozwolone.
    Dozwolone rozszerzenia są zdefiniowane w config.py.
    """
    # Sprawdzamy, czy w nazwie pliku jest kropka i pobieramy rozszerzenie.
    # Następnie konwertujemy je na małe litery i sprawdzamy, czy jest na liście dozwolonych.
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
        # 'file' to nazwa atrybutu 'name' w tagu <input type="file" name="file"> w formularzu HTML.
        if 'file' not in request.files:
            flash('Brak części pliku w żądaniu.', 'error') # Wiadomość flash dla użytkownika
            return redirect(request.url) # Przekieruj z powrotem do formularza

        file = request.files['file']

        # 2. Sprawdź, czy użytkownik faktycznie wybrał plik (pole formularza nie jest puste)
        if file.filename == '':
            flash('Nie wybrano pliku.', 'error')
            return redirect(request.url)

        # 3. Walidacja pliku (czy istnieje i ma dozwolone rozszerzenie)
        if file and allowed_file(file.filename):
            # Zabezpiecz nazwę pliku, aby uniknąć problemów bezpieczeństwa (np. path traversal).
            # `secure_filename` usuwa niebezpieczne znaki z nazwy pliku.
            filename = secure_filename(file.filename)
            # Pobierz folder do uploadu z konfiguracji aplikacji (z config.py)
            upload_folder = current_app.config['UPLOAD_FOLDER']

            # Upewnij się, że folder do zapisu plików istnieje.
            # `os.makedirs` utworzy katalogi, jeśli nie istnieją; `exist_ok=True` zapobiega błędowi,
            # jeśli katalog już jest.
            os.makedirs(upload_folder, exist_ok=True)

            # Pełna ścieżka do zapisanego pliku na serwerze
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path) # Zapisz przesłany plik na serwerze

            # 4. Utwórz nowy wpis paragonu w bazie danych
            new_receipt = Receipt(
                user_id=current_user.id, # Powiąż paragon z aktualnie zalogowanym użytkownikiem
                file_path=file_path,     # Zapisz ścieżkę do pliku w bazie danych
                status='uploaded'        # Ustaw początkowy status paragonu
            )
            db.session.add(new_receipt)
            db.session.commit() # Zatwierdź dodanie nowego paragonu do bazy danych

            # 5. Deleguj zadanie przetwarzania OCR do serwisu
            # print(f"DEBUG: Przekazuję do serwisu OCR: ID={new_receipt.id}, Ścieżka={file_path}") # Linia do debugowania
            try:
                # Wywołujemy funkcję z serwisu OCR.
                # Wartość `new_receipt.id` jest przekazywana, aby serwis mógł zaktualizować
                # konkretny wpis w bazie danych.
                # W przyszłości, dla dużych plików lub długotrwałych procesów,
                # to wywołanie powinno być asynchroniczne (np. z użyciem Celery, APScheduler lub podobnych),
                # aby nie blokować odpowiedzi HTTP dla użytkownika.
                # Na razie jest synchroniczne dla prostoty.
                process_receipt_image(new_receipt.id, file_path)
                flash('Paragon przesłany i przetwarzanie OCR rozpoczęte!', 'success')
            except Exception as e:
                # Obsługa błędów, jeśli coś pójdzie nie tak podczas uruchamiania serwisu OCR
                print(f"Błąd podczas uruchamiania serwisu OCR dla paragonu {new_receipt.id}: {e}")
                flash(f'Wystąpił błąd podczas przetwarzania paragonu: {e}', 'error')
                # Możesz zmienić status paragonu na 'error' tutaj, jeśli chcesz
                # (chociaż serwis też to robi, to jest to zabezpieczenie na wypadek, gdyby serwis się nie uruchomił poprawnie)
                db.session.rollback() # Wycofaj zmiany w sesji db, jeśli coś poszło nie tak
                new_receipt.status = 'error_during_processing_init' # Specjalny status
                db.session.commit() # Zatwierdź zmieniony status

            # Po zakończeniu przesyłania i inicjacji przetwarzania, przekieruj użytkownika
            # na listę paragonów, aby mógł zobaczyć status swojego paragonu.
            return redirect(url_for('ocr.list_receipts'))
        else:
            # Walidacja nie powiodła się (np. niewłaściwy typ pliku)
            flash('Dozwolone typy plików to: png, jpg, jpeg, gif.', 'error')
            return redirect(request.url)

    # Dla żądania GET, po prostu renderuj formularz przesyłania paragonu.
    # Użytkownik zobaczy pusty formularz do wyboru pliku.
    return render_template('ocr/upload_receipt.html')


@bp.route('/list')
@login_required
def list_receipts():
    """
    Wyświetla listę wszystkich paragonów przesłanych przez bieżącego użytkownika.
    """
    # Pobierz paragony tylko aktualnie zalogowanego użytkownika.
    # `order_by(Receipt.upload_date.desc())` sortuje paragony od najnowszego.
    # `.all()` pobiera wszystkie pasujące wyniki.
    receipts = Receipt.query.filter_by(user_id=current_user.id).order_by(Receipt.upload_date.desc()).all()
    # Renderuj szablon HTML, przekazując listę paragonów.
    return render_template('ocr/list_receipts.html', receipts=receipts)


@bp.route('/<int:receipt_id>')
@login_required
def view_receipt(receipt_id):
    """
    Wyświetla szczegółowe informacje o pojedynczym paragonie,
    w tym surowy tekst i sparsowane dane.
    Użytkownik może zobaczyć tylko swoje paragony.
    """
    # Pobierz paragon po ID, ale upewnij się, że należy do aktualnie zalogowanego użytkownika.
    # `.first_or_404()` automatycznie zwraca błąd 404 (Nie znaleziono strony),
    # jeśli paragon o danym ID nie istnieje LUB nie należy do aktualnego użytkownika.
    receipt = Receipt.query.filter_by(id=receipt_id, user_id=current_user.id).first_or_404()

    # Parsowane dane są przechowywane w bazie danych jako string JSON.
    # Metoda `get_processed_data()` w modelu Receipt (powinieneś ją mieć, konwertującą JSON string na Python dict)
    # zostanie wywołana, aby przetworzyć ten string z powrotem na słownik Pythona.
    parsed_data = receipt.get_processed_data()
    # print(f"DEBUG: Parsed data for receipt {receipt.id}: {parsed_data}") # Linia do debugowania

    # Renderuj szablon HTML, przekazując obiekt paragonu i sparsowane dane.
    return render_template('ocr/view_receipt.html', receipt=receipt, parsed_data=parsed_data)

# Dodatkowa trasa dla podglądu pliku (może być używana w przyszłości).
# Standardowo Flask serwuje pliki statyczne z katalogu 'static'.
# Jeśli chcesz, aby pliki uploadowane były dostępne przez adres URL, musisz to odpowiednio skonfigurować
# w app.py (np. app.add_url_rule('/uploads/<filename>', 'uploaded_file', build_only=True)
# lub użyć url_for('static', filename='uploads/' + filename)).
# @bp.route('/view_file/<filename>')
# @login_required
# def view_file(filename):
#     # TUTAJ TRZEBA BY BYŁO ZAINPLEMENTOWAĆ BARDZIEJ ZAAWANSOWANĄ KONTROLĘ DOSTĘPU,
#     # ABY UŻYTKOWNIK MÓGŁ WIDZIEĆ TYLKO SWOJE PLIKI.
#     # Na razie pliki są dostępne przez static/uploads jeśli tylko masz do nich ścieżkę.
#     return redirect(url_for('static', filename='uploads/' + secure_filename(filename)))