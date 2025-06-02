## Martyna: Login i Rejestracja + interfejs i backend do upload plików + parada smoków

### Etap 1: Podstawy MVP - Autoryzacja i User Dashboard

- [ ] **Formularze autentykacji:**
    - [ ] Stworzenie formularza `RegistrationForm` w `app/forms.py` (username, email, password, confirm_password).
    - [ ] Stworzenie formularza `LoginForm` w `app/forms.py` (email/username, password, remember_me).
    - [ ] Dodanie walidacji (np. unikalność username/email, długość hasła, zgodność haseł) do formularzy WTForms.
- [ ] **Trasy autentykacji:**
    - [ ] Utworzenie pliku `auth.py` w `app/routes/`.
    - [ ] Zaimplementowanie trasy `GET/POST /register` w `auth.py`: obsługa formularza, hashowanie hasła (za pomocą `bcrypt`), dodawanie użytkownika do DB.
    - [ ] Zaimplementowanie trasy `GET/POST /login` w `auth.py`: weryfikacja danych, logowanie użytkownika (`login_user` z Flask-Login).
    - [ ] Zaimplementowanie trasy `GET /logout` w `auth.py`: wylogowanie użytkownika (`logout_user`).
- [ ] **Szablony autentykacji:**
    
    - [ ] Stworzenie katalogu `auth/` w `app/templates/`.
    - [ ] Zaprojektowanie `base.html` z podstawową strukturą HTML, linkami do Bootstrap 5 i blokami `content`, `scripts`.
    - [ ] Stworzenie szablonów `auth/register.html` i `auth/login.html` dziedziczących z `base.html`, wykorzystujących Bootstrap 5 do stylizacji formularzy.
    - [ ] Wyświetlanie **komunikatów flash** (Flask `flash` messages) w `base.html`.
- [ ] **Logowanie użytkownika i strona główna:**
    
    - [ ] Stworzenie trasy `GET /` w `app/routes/shopping.py` lub `app/routes/__init__.py`, która przekieruje zalogowanego użytkownika do Strony głównej.
    - [ ] Użycie dekoratora `@login_required` do ochrony widoków wymagających zalogowania.
    - [ ] Współpraca z Tymonem w przygotowaniu Strony głównej 

### Etap 2: OCR i skanowanie paragonów - Upload i Podgląd

- [ ] **Trasy do upload'u paragonów:**
    - [ ] Utworzenie pliku `ocr.py` w `app/routes/`.
    - [ ] Zaimplementowanie trasy `GET/POST /ocr/upload` w `ocr.py`.
    - [ ] Obsługa przesłanego pliku: **walidacja typu pliku** (obraz), **bezpieczne zapisywanie pliku** w `app/static/uploads/` (z wykorzystaniem `werkzeug.utils.secure_filename`).
    - [ ] Zapisanie ścieżki do pliku i metadanych do **modelu `Receipt`** 
- [ ] **UI do upload'u paragonów:**
    - [ ] Stworzenie szablonu `ocr/upload.html` z formularzem do przesyłania plików.
    - [ ] Dodanie ProgressBar/Spinner (JavaScript) dla wizualizacji uploadu, jeśli czas pozwoli.

---

## Tymon: Rozliczenia + Główna strona + Dodawanie list + listy (interfejs) + wykresy

### Etap 1: Podstawy MVP - CRUD dla List i Produktów


- [ ] **Trasy dla list zakupów:**
	- [ ] Współpraca z Kirylem na backend
    - [ ] Utworzenie pliku `shopping.py` w `app/routes/`.
    - [ ] Zaimplementowanie trasy `GET /shopping/` (dashboard z listami użytkownika).
    - [ ] Zaimplementowanie trasy `GET/POST /shopping/create` (formularz i logika tworzenia nowej listy).
    - [ ] Zaimplementowanie trasy `GET /shopping/list/<int:id>` (szczegóły konkretnej listy).
    - [ ] Zaimplementowanie trasy `POST /shopping/list/<int:id>/add_product` (dodawanie produktu do listy ręcznie, korzystając z modelu `Product`).
    - [ ] Zaimplementowanie trasy `POST /shopping/list/<int:id>/add_participant` (dodawanie innych użytkowników do listy, korzystając z modelu `User` i relacji).
    - [ ] Zaimplementowanie trasy `POST /shopping/list/<int:id>/complete` (oznaczanie listy jako ukończonej, aktualizując **model `ShoppingList`**).
- [ ] **Szablony HTML dla list zakupów:**
    - [ ] Stworzenie katalogu `shopping/` w `app/templates/`.
    - [ ] Zaprojektowanie `shopping/dashboard.html` (wyświetlanie list, linki do tworzenia nowych).
    - [ ] Zaprojektowanie `shopping/create_list.html` (formularz tworzenia listy).
    - [ ] Zaprojektowanie `shopping/list_details.html` (wyświetlanie produktów, możliwość dodawania, przypisywania, oznaczania jako kupione).
    - [ ] Użycie Bootstrap 5 do responsywności i estetyki.
- [ ] Stworzenie głównej strony współpraca z Martyną 

### Etap 3: Rozliczenia i algorytmy

- [ ] **Algorytm rozliczania sald:**
    - [ ] Utworzenie pliku `settlement_service.py` w `app/services/`.
    - [ ] Implementacja funkcji `calculate_settlements(shopping_list_id)` w `settlement_service.py`.
    - [ ] Logika:
        - [ ] Pobranie wszystkich produktów dla danej listy (**model `Product`**).
        - [ ] Obliczenie indywidualnych sald dla każdego uczestnika (suma zapłaconych - suma przypisanych).
        - [ ] Podział na dłużników i wierzycieli.
        - [ ] Zaimplementowanie **algorytmu minimalizującego liczbę transakcji** (np. metoda "debitor-creditor matching").
        - [ ] Zapisanie wygenerowanych rozliczeń do bazy danych (**model `Settlement`**).
- [ ] **Trasy dla rozliczeń:**
    - [ ] Utworzenie pliku `settlements.py` w `app/routes/`.
    - [ ] Zaimplementowanie trasy `GET /settlements/` (dashboard rozliczeń, podsumowanie długów i kredytów dla zalogowanego użytkownika).
    - [ ] Zaimplementowanie trasy `GET /settlements/list/<int:id>/calculate` (wywołanie algorytmu rozliczania dla konkretnej listy).
    - [ ] Zaimplementowanie trasy `POST /settlements/settle/<int:id>` (oznaczanie pojedynczego rozliczenia jako opłaconego).
    - [ ] Zaimplementowanie trasy `GET /settlements/history` (historia wszystkich rozliczeń użytkownika).
- [ ] **Widoki rozliczeń:**
    - [ ] Stworzenie katalogu `settlements/` w `app/templates/`.
    - [ ] Zaprojektowanie `settlements/dashboard.html` z jasnym podsumowaniem "Kto komu ile jest winien".
    - [ ] Zaprojektowanie `settlements/history.html` z tabelą historycznych rozliczeń.
- [ ] **Wykresy i statystyki:**
    - [ ] Osadzenie biblioteki **Chart.js** w `base.html` lub w dedykowanym pliku JS w `app/static/js/`.
    - [ ] Napisanie skryptów JavaScript w `app/static/js/` do renderowania wykresów:
        - [ ] Wykres słupkowy podsumowujący wydatki na listach.
        - [ ] Wykres kołowy dla proporcji długów/kredytów.
    - [ ] Integracja danych z backendu (poprzez AJAX requests do API lub wbudowane dane w Jinja2 templates) z wykresami Chart.js.

---

## Kiryl: Powiadomienia Email + Backend (dodawanie list i zarządzanie list) + CSV eksport

### Etap 4: Powiadomienia i Integracje

- [ ] **Konfiguracja Flask-Mail:**
    - [ ] Instalacja Flask-Mail.
    - [ ] Konfiguracja **SMTP** w `config.py` (MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER).
- [ ] **Usługa powiadomień email:**
    - [ ] Utworzenie pliku `notification_service.py` w `app/services/`.
    - [ ] Zaimplementowanie funkcji `send_email(to, subject, template, **kwargs)` w `notification_service.py`, która renderuje szablon HTML i wysyła e-mail.
    - [ ] Stworzenie prostych **szablonów email** w `app/templates/emails/` (np. `settlement_reminder.html`, `new_list_notification.html`).
- [ ] **Automatyczne przypomnienia o płatnościach:**
    - [ ] Instalacja **APScheduler**.
    - [ ] Konfiguracja APScheduler w `run.py` lub dedykowanym pliku do uruchamiania zadań w tle.
    - [ ] Zaimplementowanie zadania (job) APScheduler, które cyklicznie sprawdza zaległe rozliczenia (**model `Settlement`**, `is_settled=False`) i wysyła przypomnienia e-mail do dłużników.
    - [ ] Określenie logiki, kiedy wysyłać przypomnienie (np. po X dniach od wygenerowania rozliczenia).
- [ ] **Trasy dla powiadomień:**
    - [ ] Utworzenie pliku `notifications.py` w `app/routes/`.
    - [ ] Zaimplementowanie trasy `GET /notifications/` (opcjonalnie: lista wysłanych powiadomień lub ustawienia powiadomień).
    - [ ] Zaimplementowanie trasy `POST /notifications/send/<int:settlement_id>` (ręczne wysłanie przypomnienia dla konkretnego rozliczenia).
    - [ ] Zaimplementowanie trasy `GET/POST /notifications/settings` (opcjonalnie: ustawienia preferencji powiadomień dla użytkownika).
- [ ] **Backend (dodawanie list i zarządzanie list) - uzupełnienie:**
    - [ ] Ścisła współpraca z Tymonem w celu zapewnienia, że wszystkie operacje na **listach zakupów** i **produktach** (CRUD) są w pełni zaimplementowane na poziomie backend.
    - [ ]  Stworzenie serwisu zajmującego się logiką dodawania do list zakupowych i edytowania oraz archiwizacji
- [ ] **Formularze dla list i produktów:**
    - [ ] Stworzenie formularzy w `app/forms.py` dla:
        - [ ] `ShoppingListForm` (nazwa listy).
        - [ ] `ProductForm` (nazwa produktu, cena, przypisanie do osoby, kto zapłacił).
        - [ ] `AddParticipantForm` (wybór istniejących użytkowników).
- [ ] **Eksport danych do CSV:**
    - [ ] Zaimplementowanie trasy `GET /settlements/export/csv` w `app/routes/settlements.py`.
    - [ ] Logika eksportu:
        - [ ] Pobranie danych o rozliczeniach (lub innych istotnych danych, np. wszystkich produktów z danej listy) z bazy danych.
        - [ ] Wykorzystanie **modułu `csv` Pythona** do zapisu danych do bufora.
        - [ ] Zwrócenie bufora jako **pliku CSV** do pobrania przez użytkownika (Flask `send_file`).

---

## Kacper: OCR + Migracje Danych + Git

### Etap 1: Konfiguracja i Git (współpraca z całym zespołem)

- [ ] **Git:**
    - [ ] Ustalenie i przypomnienie zespołowi o konwencjach nazewnictwa gałęzi (branches) i commitów.
    - [ ] Upewnienie się, że każdy członek zespołu rozumie podstawy pracy z Git (pull, push, branch, merge).
    - [ ] Aktywne wspieranie zespołu w **rozwiązywaniu konfliktów scalania** (merge conflicts).
    - [ ] Dbanie o aktualizację `requirements.txt` przy dodawaniu nowych zależności.
### Etap 1: Modele Danych + Migracje Danych
- [ ] **Modele Danych (w `app/models.py`):**
    - [ ] **Model `User` (Użytkownicy):**
        - [ ] Zdefiniowanie pól: `id` (klucz główny, integer), `username` (string, unikalny, niepusty), `email` (string, unikalny, niepusty), `password_hash` (string, niepusty), `created_at` (datetime, domyślna wartość: aktualna data/czas UTC).
        - [ ] Zapewnienie, że klasa `User` dziedziczy z `UserMixin` z Flask-Login.
        - [ ] Dodanie metod `set_password(password)` i `check_password(password)` do hashowania/sprawdzania haseł z użyciem `bcrypt`.
        - [ ] Zdefiniowanie relacji `one-to-many` do `ShoppingList` (jako twórca), `Product` (jako przypisany i płacący), `Settlement` (jako dłużnik i wierzyciel), `Receipt`.
    - [ ] **Model `ShoppingList` (Lista zakupów):**
        - [ ] Zdefiniowanie pól: `id` (klucz główny), `name` (string, niepusty), `created_by` (integer, klucz obcy do `User.id`), `created_at` (datetime, domyślna wartość), `is_completed` (boolean, domyślnie False).
        - [ ] Zdefiniowanie relacji `one-to-many` do `Product` i `Settlement`.
        - [ ] Zdefiniowanie relacji `many-to-many` z `User` dla uczestników listy (przez tabelę pośrednią `shopping_list_participants` - patrz niżej).
    - [ ] **Model `Product` (Produkty na liście):**
        - [ ] Zdefiniowanie pól: `id` (klucz główny), `name` (string, niepusty), `price` (Decimal(10, 2), niepusty), `shopping_list_id` (integer, klucz obcy do `ShoppingList.id`), `assigned_to` (integer, klucz obcy do `User.id`), `paid_by` (integer, klucz obcy do `User.id`), `is_purchased` (boolean, domyślnie False).
        - [ ] Zdefiniowanie relacji `many-to-one` do `ShoppingList` i `User` (dla `assigned_to` i `paid_by`).
    - [ ] **Model `Receipt` (Paragony):**
        - [ ] Zdefiniowanie pól: `id` (klucz główny), `user_id` (integer, klucz obcy do `User.id`), `file_path` (string, niepusty), `upload_date` (datetime, domyślna wartość), `status` (string, np. 'uploaded', 'processing', 'processed', 'error'), `raw_text` (text, opcjonalnie - na wypadek przechowywania surowego tekstu z OCR), `processed_data` (JSON/Text, na wypadek przechowywania sparsowanych danych).
        - [ ] Zdefiniowanie relacji `many-to-one` do `User`.
        - [ ] Opcjonalnie: pole do relacji z `Product` jeśli produkty z paragonu mają być bezpośrednio powiązane z modelem `Product` (np. `receipt_id` w `Product`).
    - [ ] **Model `Settlement` (Rozliczenia):**
        - [ ] Zdefiniowanie pól: `id` (klucz główny), `shopping_list_id` (integer, klucz obcy do `ShoppingList.id`), `debtor_id` (integer, klucz obcy do `User.id`, kto jest winien), `creditor_id` (integer, klucz obcy do `User.id`, komu jest winien), `amount` (Decimal(10, 2), niepusty), `is_settled` (boolean, domyślnie False), `created_at` (datetime, domyślna wartość).
        - [ ] Zdefiniowanie relacji `many-to-one` do `ShoppingList` oraz dwóch relacji `many-to-one` do `User` (dla dłużnika i wierzyciela).
    - [ ] **Tabela pośrednia `shopping_list_participants` (dla relacji many-to-many):**
        - [ ] Utworzenie tabeli asocjacyjnej dla relacji `many-to-many` między `User` a `ShoppingList` (uczestnicy listy).
        - [ ] Zdefiniowanie pól: `user_id` (klucz obcy do `User.id`), `shopping_list_id` (klucz obcy do `ShoppingList.id`).
        - [ ] Ustawienie obu pól jako klucza głównego tabeli.
    - [ ] Dodanie **indeksów do pól kluczy obcych** dla optymalizacji zapytań (np. `db.Index('idx_shopping_list_id', Product.shopping_list_id)`).
- [ ] **Migracje Danych (Flask-Migrate):**
    - [ ] **Inicjalizacja migracji:** Jeśli jeszcze nie zrobiono, wykonanie `flask db init` w katalogu głównym projektu, aby utworzyć folder `migrations/`.
    - [ ] **Tworzenie pierwszej migracji:** Po zdefiniowaniu wszystkich powyższych modeli, wykonanie `flask db migrate -m "Create all core tables"` w terminalu. To wygeneruje skrypt migracji w folderze `migrations/versions/`.
    - [ ] **Przejrzenie i weryfikacja migracji:** Sprawdzenie wygenerowanego skryptu migracji, aby upewnić się, że poprawnie odzwierciedla definicje modeli (tworzenie tabel, pól, kluczy obcych, indeksów).
    - [ ] **Zastosowanie migracji:** Wykonanie `flask db upgrade` w terminalu, aby utworzyć tabele w bazie danych (SQLite lub PostgreSQL).
    - [ ] **Obsługa zmian w modelach:** Przy każdej przyszłej zmianie w definicjach modeli (np. dodanie nowego pola, zmiana typu danych, dodanie nowego modelu), ponowne wykonanie `flask db migrate -m "Opis_zmiany"` i `flask db upgrade`.
    - [ ] **Testowanie migracji:** Upewnienie się, że migracje działają poprawnie zarówno przy `upgrade`, jak i (opcjonalnie) `downgrade`.
### Etap 2: OCR i skanowanie paragonów - Przetwarzanie i Parsing

- [ ] **Preprocessing obrazów (OCR Service):**
    - [ ] Utworzenie pliku `ocr_service.py` w `app/services/`.
    - [ ] Zaimplementowanie funkcji `preprocess_image(image_path)` w `OCRService` z wykorzystaniem **OpenCV (`cv2`)** i **Pillow**.
    - [ ] Kroki preprocessingowe:
        - [ ] Wczytanie obrazu.
        - [ ] Konwersja do skali szarości.
        - [ ] Binaryzacja (np. Otsu's thresholding) lub adaptacyjne progowanie.
        - [ ] Opcjonalnie: deskewing (prostowanie przekrzywionych obrazów), redukcja szumów.
    - [ ] Zapisanie przetworzonego obrazu tymczasowo lub przekazanie go bezpośrednio do Tesseracta.
- [ ] **Ekstrakcja tekstu (OCR Service):**
    - [ ] Zaimplementowanie funkcji `extract_text(image_path)` w `OCRService`.
    - [ ] Wykorzystanie **`pytesseract.image_to_string`** na przetworzonym obrazie.
    - [ ] Określenie języka (`lang='pol'`) dla Tesseracta.
- [ ] **Parser tekstu paragonów (OCR Service):**
    - [ ] Zaimplementowanie funkcji `parse_receipt(raw_text)` w `OCRService`.
    - [ ] Wykorzystanie **wyrażeń regularnych (`re` module)** do:
        - [ ] Wyodrębniania nazw produktów.
        - [ ] Wyodrębniania cen (w formacie `XX,YY` lub `XX.YY`).
        - [ ] Opcjonalnie: identyfikacji sumy końcowej, VAT.
    - [ ] Strukturyzowanie wyników w postaci listy słowników (np. `[{'name': 'Mleko', 'price': 3.49}]`).
- [ ] **Integracja OCR z trasami:**
    - [ ] Współpraca z Martyną w celu integracji `OCRService` z trasą `POST /ocr/upload`. Po uploadzie i zapisaniu pliku, wywołanie `OCRService.extract_text` i `OCRService.parse_receipt`.
    - [ ] Zapisanie surowego tekstu z OCR i/lub sparsowanych produktów do **modelu `Receipt`** lub tymczasowej sesji.
- [ ] **Korekta wyników OCR przez użytkownika:**
    - [ ] Współpraca z Martyną przy trasie `GET /ocr/receipt/<int:id>` i `POST /ocr/receipt/<int:id>/correct`.
    - [ ] Wyświetlanie surowego tekstu i/lub sparsowanych produktów w interfejsie.
    - [ ] Umożliwienie użytkownikowi **edycji nazw produktów, cen, dodawania/usuwania pozycji**.
    - [ ] Zapisanie skorygowanych danych do bazy danych.
    - [ ] Opcjonalnie: Zaimplementowanie tras `POST /ocr/receipt/<int:id>/assign` do przypisywania produktów z paragonu do listy zakupów i konkretnych użytkowników.

---

## Dodatkowe Zadania dla Zespołu:

### Interfejs użytkownika odzyskiwanie hasła:

- [ ] **Backend:**
    - [ ] Dodanie pola `reset_token` do **modelu `User`** (opcjonalnie, lub użycie tabeli tymczasowej dla tokenów).
    - [ ] Zaimplementowanie trasy `GET/POST /auth/reset_password_request` (żądanie resetu, wysyłanie tokena na email).
    - [ ] Zaimplementowanie trasy `GET/POST /auth/reset_password/<token>` (ustawianie nowego hasła).
    - [ ] Logika **generowania i weryfikacji tokenów** (np. za pomocą `itsdangerous` lub prostego generowania unikalnego stringa i sprawdzania czasu ważności).
    - [ ] Integracja z `notification_service.py` (Kiryl) do wysyłki e-maili z linkiem do resetu hasła.
- [ ] **Formularze:**
    - [ ] Stworzenie formularza `PasswordResetRequestForm` (email).
    - [ ] Stworzenie formularza `PasswordResetForm` (nowe hasło, potwierdzenie).
- [ ] **Szablony:**
    - [ ] Zaprojektowanie `auth/reset_password_request.html` i `auth/reset_password.html`.
    - [ ] Stworzenie szablonu email do resetu hasła w `app/templates/emails/`.

### Testy do każdego modułu:

- [ ] **Testy jednostkowe (dla każdego modułu):**
    - [ ] Konfiguracja Pytest (lub unittest) w projekcie.
    - [ ] **Serwisy:** Napisanie testów dla `OCRService`, `SettlementService`, `NotificationService` (mockowanie zależności zewnętrznych).
    - [ ] **Formularze:** Napisanie testów dla walidacji formularzy.
- [ ] **Testy integracyjne:**
    - [ ] Napisanie testów, które symulują interakcje użytkownika (np. rejestracja -> logowanie -> utworzenie listy -> dodanie produktu).
    - [ ] Testowanie przepływów danych między trasami, serwisami i bazą danych.
- [ ] **Pokrycie kodu:**
    - [ ] Monitorowanie pokrycia kodu testami za pomocą `pytest-cov`.
    - [ ] Dążenie do co najmniej 80% pokrycia dla kluczowych modułów.
