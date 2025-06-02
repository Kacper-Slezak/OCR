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
