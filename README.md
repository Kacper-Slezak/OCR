## Cel projektu

Aplikacja webowa do współdzielenia i rozliczania kosztów zakupów grupowych. Użytkownicy tworzą listy zakupów, przypisują produkty do osób, skanują paragony, a aplikacja automatycznie rozlicza koszty i wysyła przypomnienia o płatnościach.

---

## Stack technologiczny

### Backend

- **Python 3.10+** + **Flask**
- **SQLAlchemy** (ORM) + **SQLite/PostgreSQL**
- **Flask-Login** (autoryzacja)
- **Flask-Mail** (powiadomienia email)

### OCR i przetwarzanie

- **Tesseract OCR** + **pytesseract**
- **OpenCV** (pre-processing obrazów)
- **Pillow** (manipulacja obrazów)

### Frontend

- **Jinja2** templates + **Bootstrap 5**
- **JavaScript** (vanilla + AJAX)
- **Chart.js** (wykresy i statystyki)

### Integracje

- **Twilio** (SMS) lub **Flask-Mail** (email)
- **Stripe API** (płatności online)
- **Requests** (API calls)

---

## Struktura projektu

```
shopping-app/
├── app/
│   ├── __init__.py
│   ├── models.py               # Modele bazy danych
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py             # Logowanie/rejestracja
│   │   ├── shopping.py         # Listy zakupów
│   │   ├── ocr.py              # Skanowanie paragonów
│   │   ├── settlements.py      # Rozliczenia
│   │   └── notifications.py    # Powiadomienia
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ocr_service.py      # Logika OCR
│   │   ├── settlement_service.py # Algorytmy rozliczeń
│   │   ├── notification_service.py # Email/SMS
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── shopping/
│   │   ├── ocr/
│   │   └── settlements/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── uploads/           # Przesłane paragony
│   └── forms.py               # Formularze WTF
├── migrations/                # Migracje bazy danych
├── tests/                     # Testy (opcjonalnie)
├── config.py
├── requirements.txt
└── run.py
```

---
### Osoby:
- Issues
	- Git
- Martyna:
	- Login i Rejestracja + interfejs i backend do upload plików + parada smoków 
- Tymon
	- Rozliczenia + Główna strona + Dodawanie list + listy (interfejs) + wykresy
- Kiryl
	- Powiadomienia Email + Backend(dodawanie list i zarządzanie list) + CSV eksport
- Kacper
	-  OCR + Modele Danych + Migracje Danych + Git
- Dodatkowo:
	- Interfejs użytkownika odzyskiwanie hasła
	- Testy do każdego
---

## Plan implementacji (etap po etapie)

### Etap 1: Podstawy MVP 

**Cel**: Działająca aplikacja z logowaniem i podstawowym CRUD

**Do zrobienia**:

1. Konfiguracja projektu Flask + SQLAlchemy
2. Modele bazy danych (User, ShoppingList, Product)
3. System autentykacji (rejestracja/logowanie/logout)
4. Podstawowe template'y HTML z Bootstrap
5. Dashboard użytkownika
6. CRUD dla list zakupów i produktów

**Funkcjonalności**:

- Rejestracja i logowanie użytkowników
- Tworzenie i wyświetlanie list zakupów
- Dodawanie produktów do listy (ręcznie)
- Przypisywanie produktów do osób

### Etap 2: OCR i skanowanie paragonów

**Cel**: Automatyczne rozpoznawanie paragonów

**Do zrobienia**:

1. Model Receipt + upload plików
2. Integracja Tesseract OCR + OpenCV
3. Preprocessing obrazów (poprawa jakości)
4. Parser tekstu paragonów (regex)
5. UI do uploadu i podglądu paragonów
6. Korekta wyników OCR przez użytkownika

**Funkcjonalności**:

- Upload zdjęć paragonów
- Automatyczne wyciąganie produktów i cen
- Ręczna korekta wyników OCR
- Przypisywanie produktów z paragonu do listy

### Etap 3: Rozliczenia i algorytmy 

**Cel**: Automatyczne obliczanie rozliczeń

**Do zrobienia**:

1. Model Settlement
2. Algorytm obliczania sald (minimalizacja transakcji)
3. Widoki rozliczeń i dashboard
4. Historia płatności
5. System oznaczania rozliczeń jako opłacone

**Funkcjonalności**:

- Automatyczne obliczanie kto ile komu jest winien
- Optymalizacja liczby transakcji
- Dashboard z podsumowaniem długów
- Historia wszystkich rozliczeń

### Etap 4: Powiadomienia i integracje 

**Cel**: Automatyzacja powiadomień i płatności

**Do zrobienia**:

1. Model Notification
2. Integracja Flask-Mail (email)
3. Integracja Twilio (SMS) - opcjonalnie
4. Scheduler powiadomień (cron job / APScheduler)
5. Integracja Stripe (płatności online) - opcjonalnie
6. Eksport danych (CSV/PDF)

**Funkcjonalności**:

- Automatyczne przypomnienia o płatnościach
- Powiadomienia email/SMS
- Płatności online przez Stripe (opcjonalnie)
- Eksport rozliczeń do plików

### Etap 5: Dopracowanie UI/UX 

**Cel**: Polski produkt gotowy do prezentacji

**Do zrobienia**:

1. Responsywny design (mobile-first)
2. Lepsze formularze i walidacja
3. Komunikaty flash i obsługa błędów
4. Wykresy i statystyki (Chart.js)
5. Testy podstawowe
6. Deployment na Heroku/Railway
7. Dokumentacja

---

## Kluczowe widoki (routes)

### Autentykacja (`/auth/`)

- `GET/POST /register` - Rejestracja
- `GET/POST /login` - Logowanie
- `GET /logout` - Wylogowanie

### Listy zakupów (`/shopping/`)

- `GET /` - Dashboard z listami
- `GET/POST /create` - Tworzenie nowej listy
- `GET /list/<id>` - Szczegóły listy
- `POST /list/<id>/add_product` - Dodawanie produktu
- `POST /list/<id>/add_participant` - Dodawanie uczestnika
- `POST /list/<id>/complete` - Oznaczanie jako ukończone

### OCR i paragony (`/ocr/`)

- `GET/POST /upload` - Upload paragonu
- `GET /receipt/<id>` - Podgląd paragonu
- `POST /receipt/<id>/correct` - Korekta OCR
- `POST /receipt/<id>/assign` - Przypisanie produktów

### Rozliczenia (`/settlements/`)

- `GET /` - Dashboard rozliczeń
- `GET /list/<id>/calculate` - Obliczanie dla listy
- `POST /settle/<id>` - Oznaczanie jako opłacone
- `GET /history` - Historia rozliczeń
- `GET /export/<format>` - Eksport danych

### Powiadomienia (`/notifications/`)

- `GET /` - Lista powiadomień
- `POST /send/<settlement_id>` - Wysłanie przypomnienia
- `GET/POST /settings` - Ustawienia powiadomień
---

## Kluczowe funkcje (priorytet)

### **Must-have** 

1. Rejestracja i logowanie użytkowników
2. Tworzenie list zakupów + dodawanie uczestników
3. Dodawanie produktów do list (ręcznie)
4. Podstawowe OCR paragonów
5. Algorytm rozliczania kosztów
6. Widok "kto komu ile jest winien"

###  **Should-have** 

7. Automatyczne powiadomienia email
8. Historia rozliczeń
9. Dashboard z wykresami
10. Export do CSV

###  **Could-have** 

11. SMS notifications
12. Integracja płatnicza (Stripe)
13. Mobile-friendly design
14. Zaawansowane filtry i search

---
## Lista zadań na start

### Konfiguracja środowiska:

- [ ]  Stworzenie wirtualnego środowiska Python
- [ ]  Instalacja Flask i podstawowych zależności
- [ ]  Konfiguracja bazy danych SQLite
- [ ]  Struktura katalogów projektu
- [ ]  Inicjalizacja git repository

### Pierwszy milestone (Etap 1):
	
- [ ]  Model User + system autentykacji
- [ ]  Template base.html z Bootstrap
- [ ]  Formularze logowania/rejestracji
- [ ]  Model ShoppingList + CRUD operations
- [ ]  Model Product + podstawowe operacje
- [ ]  Dashboard użytkownika
- [ ]  Testy podstawowej funkcjonalności

### Drugi milestone (Etap 2):

- [ ]  Model Receipt + upload plików
- [ ]  Integracja Tesseract OCR
- [ ]  Preprocessing obrazów z OpenCV
- [ ]  Parser tekstu paragonów
- [ ]  UI dla uploadu paragonów
- [ ]  System korekty wyników OCR

---

## Wskazówki techniczne

### Requirements.txt:

```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.1
Flask-Mail==0.9.1
Flask-Migrate==4.0.5
WTForms==3.1.0
bcrypt==4.0.1
python-dotenv==1.0.0
pytesseract==0.3.10
opencv-python==4.8.1.78
Pillow==10.1.0
requests==2.31.0
APScheduler==3.10.4
stripe==7.8.0
twilio==8.10.3
```

___
## Przykłady kodu

### Główne tabele

#### User (Użytkownicy)

```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

#### ShoppingList (Lista zakupów)

```python
class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_completed = db.Column(db.Boolean, default=False)
```

#### Product (Produkty na liście)

```python
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Decimal(10, 2))
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'))
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    paid_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_purchased = db.Column(db.Boolean, default=False)
```

#### Settlement (Rozliczenia)

```python
class Settlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'))
    debtor_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # kto jest winien
    creditor_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # komu jest winien
    amount = db.Column(db.Decimal(10, 2), nullable=False)
    is_settled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Algorytm rozliczania (Backend)

```python
def calculate_settlements(shopping_list_id):
    """Oblicza optymalne rozliczenia minimalizując liczbę transakcji"""
    products = Product.query.filter_by(
        shopping_list_id=shopping_list_id,
        is_purchased=True
    ).all()
    
    # Krok 1: Oblicz salda dla każdego użytkownika
    balances = {}  # user_id: balance (+ = kredytodawca, - = dłużnik)
    
    for product in products:
        paid_by = product.paid_by
        assigned_to = product.assigned_to
        amount = float(product.price)
        
        # Kto zapłacił dostaje +
        balances[paid_by] = balances.get(paid_by, 0) + amount
        # Kto miał kupić dostaje -
        balances[assigned_to] = balances.get(assigned_to, 0) - amount
    
    # Krok 2: Podział na kredytodawców i dłużników
    creditors = [(user_id, amount) for user_id, amount in balances.items() if amount > 0.01]
    debtors = [(user_id, -amount) for user_id, amount in balances.items() if amount < -0.01]
    
    # Krok 3: Algorytm minimalizacji transakcji
    settlements = []
    
    for debtor_id, debt_amount in debtors:
        remaining_debt = debt_amount
        
        for i, (creditor_id, credit_amount) in enumerate(creditors):
            if remaining_debt <= 0.01:
                break
                
            # Ile może zostać uregulowane
            settlement_amount = min(remaining_debt, credit_amount)
            
            if settlement_amount > 0.01:
                settlements.append({
                    'debtor_id': debtor_id,
                    'creditor_id': creditor_id,
                    'amount': round(settlement_amount, 2)
                })
                
                # Aktualizuj salda
                remaining_debt -= settlement_amount
                creditors[i] = (creditor_id, credit_amount - settlement_amount)
    
    return settlements
```

### OCR Service (OCR) 

```python
class OCRService:
    def preprocess_image(self, image_path):
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        return thresh

    def extract_text(self, image_path):
        processed_img = self.preprocess_image(image_path)
        text = pytesseract.image_to_string(processed_img, lang='pol')
        return text

    def parse_receipt(self, text):
        # Regex do wyciągania produktów i cen
        product_pattern = r'([A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż\s]+)\s+(\d+,\d{2})'
        matches = re.findall(product_pattern, text)
        return [{'name': name.strip(), 'price': float(price.replace(',', '.'))} 
                for name, price in matches]
```


---

## Ryzyka

###  **Główne ryzyka:**

1. **OCR może być niestabilny** → Możliwość korekty
2. **Integracje płatnicze skomplikowane** → Zrób jako opcjonalne na koniec
3. **Algorytmy rozliczania** → Optymalizacja może być nie potrzebna
4. **Deployment może być problematyczny** → Użyj Heroku/Railway (proste)

###  **Plan B:**

- Jeśli OCR nie działa dobrze → dodaj ręczne wprowadzanie paragonów
- Jeśli płatności za trudne → zostaw przy powiadomieniach email
- Jeśli integracja pomiędzy użytkownikami nie działa → to prosty jedno osobowy z wpisywaniem osób ręcznie a nie dodawaniem z listy znajomych czy czegoś

___
## Możliwy podział zespołu

###  **Backend + Logika rozliczeń** 

- Modele danych (User, ShoppingList, Product, Payment)
- API REST dla wszystkich operacji CRUD
- **Algorytmy rozliczania** (kto ile komu jest winien)
- System autoryzacji (sesje użytkowników)
- Logika automatycznych przypomnień

###  **Frontend + UX** 

- Responsive web interface (HTML, CSS, JavaScript)
- Formularze (dodawanie list, produktów, użytkowników)
- **Dashboard** z podsumowaniami i wykresami
- Interfejs do przeglądania skanów paragonów
- AJAX dla dynamicznych aktualizacji

###  **OCR + Przetwarzanie obrazów** 

- **Integracja Tesseract OCR**
- Preprocessing obrazów (OpenCV)
- **Parser paragonów** (wyciąganie produktów i cen)
- Upload i zarządzanie zdjęciami paragonów
- Walidacja i korekta wyników OCR

###  **Integracje + Powiadomienia** (Kiryl)

- **System powiadomień** (email + SMT)
+
- **Automatyczne przypomnienia** o płatnościach
- Export danych (CSV)

