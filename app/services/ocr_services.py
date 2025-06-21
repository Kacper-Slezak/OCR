import numpy as np
import cv2
from PIL import Image
import pytesseract
import os
import re
from flask import current_app as app
import json


def set_tesseact_path():
    tesseract_path = app.config.get('TESSERACT_PATH')
    print(f"DEBUG: TESSERACT_PATH z config.py: '{tesseract_path}'")
    if tesseract_path and os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        print(f"DEBUG: Ustawiono pytesseract.pytesseract.tesseract_cmd na: '{tesseract_path}'")
    else:
        print(f'WARNING: No tesseract path found at {tesseract_path}. Configure .env variables first.')
        print(f"DEBUG: Czy ścieżka istnieje według os.path.exists? {os.path.exists(tesseract_path)}")
        print(f"DEBUG: Typ tesseract_path: {type(tesseract_path)}")


def preprocess_image(image_path):
    """
    NOWA, UPROSZCZONA I BARDZIEJ ROBUSTNA funkcja preprocessingu.
    Skupia się na kluczowych krokach: konwersji do skali szarości,
    binaryzacji i zapewnieniu właściwego formatu (czarny tekst na białym tle).
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Nie można załadować obrazu: {image_path}")

        # Krok 1: Konwersja do skali szarości
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Krok 2 (Opcjonalnie, ale zalecane): Korekcja przekrzywienia (Deskewing)
        # Ta część jest w porządku i warto ją zostawić.
        try:
            coords = np.column_stack(np.where(gray > 0))
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            if abs(angle) > 1 and abs(angle) < 45:  # Stosuj rotację tylko dla sensownych kątów
                (h, w) = gray.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                print(f"DEBUG: Skorygowano przekrzywienie obrazu o {angle:.2f} stopni.")
        except Exception as e:
            print(f"WARNING: Nie udało się skorygować przekrzywienia: {e}")

        # Krok 3: Binaryzacja z metodą Otsu - ZNACZNIE LEPSZA NIŻ POPRZEDNIA METODA
        # Metoda Otsu automatycznie znajduje najlepszy próg do oddzielenia tekstu od tła.
        # Jest to o wiele bardziej niezawodne niż skomplikowana kaskada filtrów.
        thresh_value, thresh_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        print(f"DEBUG: Użyto progu Otsu o wartości: {thresh_value}")

        # Krok 4: Zapewnienie, że tekst jest czarny na białym tle (NAJWAŻNIEJSZE!)
        # Tesseract działa najlepiej w tym trybie. Musimy sprawdzić, czy tło jest białe.
        # Obliczamy średni kolor. Jeśli jest bliższy czerni (0) niż bieli (255), tło jest czarne.
        if np.mean(thresh_image) < 128:
            print("DEBUG: Wykryto biały tekst na czarnym tle. Inwertuję obraz.")
            thresh_image = cv2.bitwise_not(thresh_image)  # Inwersja kolorów

        # Zapisz obraz do weryfikacji. Zawsze sprawdzaj ten plik!
        # Powinieneś zobaczyć czysty, czarny tekst na białym tle.
        debug_path = os.path.join(os.path.dirname(image_path), f"debug_preprocessed_{os.path.basename(image_path)}")
        cv2.imwrite(debug_path, thresh_image)
        print(f"DEBUG: Zapisano obraz po preprocessingu do: {debug_path}")

        return Image.fromarray(thresh_image)

    except Exception as e:
        print(f"FATAL: Krytyczny błąd podczas przetwarzania obrazu '{image_path}': {e}")
        return None


def run_ocr(image_path):
    """
    Enhanced OCR with multiple configuration attempts.
    """
    set_tesseact_path()

    # Store original environment variables
    original_tmpdir = os.environ.get('TMPDIR')
    original_temp = os.environ.get('TEMP')
    original_tmp = os.environ.get('TMP')

    tesseract_temp_dir = app.config.get('TESSERACT_TEMP_DIR')
    if not tesseract_temp_dir:
        return "ERROR: Tesseract temporary directory not configured."

    os.makedirs(tesseract_temp_dir, exist_ok=True)

    try:
        # Set temporary environment variables
        os.environ['TMPDIR'] = tesseract_temp_dir
        os.environ['TEMP'] = tesseract_temp_dir
        os.environ['TMP'] = tesseract_temp_dir

        preprocessed_image = preprocess_image(image_path)
        if preprocessed_image is None:
            return "ERROR: Image preprocessing failed."

        # Try multiple OCR configurations
        configs = [
            '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĄĆĘŁŃÓŚŹŻąćęłńóśźż.,:-+/()%|[]{}',
            '--oem 3 --psm 4',
            '--oem 3 --psm 6',
            '--oem 1 --psm 6'
        ]

        best_result = ""
        best_confidence = 0

        for config in configs:
            try:
                result = pytesseract.image_to_string(preprocessed_image, lang='pol', config=config)
                # Simple confidence metric based on text length and readable characters
                confidence = len(result) + len(re.findall(r'[A-Za-z]', result))

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_result = result

            except Exception as e:
                print(f"OCR config failed: {e}")
                continue

        return best_result if best_result else "ERROR: All OCR configurations failed."

    except pytesseract.TesseractNotFoundError:
        return "ERROR: Tesseract not found. Make sure it's installed and path is configured."
    except Exception as e:
        return f"OCR failed: {e}"
    finally:
        # Restore original environment variables
        if original_tmpdir is not None:
            os.environ['TMPDIR'] = original_tmpdir
        else:
            os.environ.pop('TMPDIR', None)

        if original_temp is not None:
            os.environ['TEMP'] = original_temp
        else:
            os.environ.pop('TEMP', None)

        if original_tmp is not None:
            os.environ['TMP'] = original_tmp
        else:
            os.environ.pop('TMP', None)


def parse_ocr(raw_text):
    from decimal import Decimal

    parsed_data = {
        "items": [],
        "total": None,
        "date": None,
        "store": None,
        "raw_text": raw_text
    }

    def fix_common_ocr_mistakes(line):
        return (
            line.replace('×', 'x')
            .replace('X', 'x')
            .replace('«', 'x')
            .replace('»', 'x')
            .replace(';', '')
            .replace('|', '')
            .replace('KO,', '')
            .replace('Txd', '1x')
            .replace('Tx', '1x')
            .replace('x ', 'x')
            .replace(', ', ',')
            .replace(',[', ',')
            .replace('[', '')
            .replace(']', '')
            .replace('(', '')
            .replace(')', '')
            .replace('Ć', '')
            .replace('©', '')
        )

    def normalize_price(price_str):
        if not price_str:
            return None
        s = price_str.strip().replace(',', '.')
        s = re.sub(r'[ABCćĆ©]$', '', s)

        # Jeśli liczba wygląda na 3 cyfry bez kropki, zinterpretuj jako np. "249" → "2.49"
        if re.fullmatch(r'\d{3}', s):
            s = f"{s[:-2]}.{s[-2:]}"

        # Jeśli liczba wygląda na 4 cyfry bez kropki, może być np. "1249" → "12.49"
        if re.fullmatch(r'\d{4}', s):
            s = f"{s[:-2]}.{s[-2:]}"

        m = re.search(r'(\d+)\.?(\d{2})', s)
        if m:
            return f"{m.group(1)}.{m.group(2)}"
        return None

    def extract_total(text):
        m = re.search(r'SUMA\s+PLN\s+([0-9]+[.,]\d{2})', text, re.IGNORECASE)
        if m:
            p = normalize_price(m.group(1))
            try:
                return str(Decimal(p))
            except:
                pass
        return None

    def clean_name(n):
        # Remove common OCR artifacts or noise that might be attached to names
        n = re.sub(r'[|()©*„”\'`~]', '', n) # Add more common OCR errors
        n = re.sub(r'\s+[ABCćĆ©]$', '', n) # Remove single category letters at the end
        n = re.sub(r'\s+\d+x\d+[.,]\d{2}', '', n) # Remove "qty x price" if it got stuck in name
        n = re.sub(r'\s+\d+[.,]\d{2}$', '', n) # Remove standalone price at the end
        n = re.sub(r'\s+', ' ', n).strip() # Normalize spaces
        # Remove numbers that are clearly part of a transaction ID or date at the end of a line
        n = re.sub(r'\s+\d{4,}$', '', n) # e.g., "Product Name 12345"
        return n

    def is_valid_name(n):
        if not n: return False
        n_cleaned = n.strip()
        if len(n_cleaned) < 3: return False # Minimum length for a product name
        # Check if the name consists mostly of non-alphanumeric characters or only numbers
        letters = len(re.findall(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', n_cleaned))
        digits = len(re.findall(r'\d', n_cleaned))
        symbols = len(re.findall(r'[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\d\s]', n_cleaned))

        # A valid name should have a reasonable number of letters compared to digits/symbols
        if letters == 0 and digits > 0: return False # Just numbers
        if letters < digits / 2 : return False # Significantly more digits than letters
        if letters == 0 and symbols > 0: return False # Just symbols
        if re.match(r'^\d', n_cleaned): return False # Does not start with a digit (unless it's a known product code, but generally not)

        # Avoid lines that are just single letters or very short common words that might be OCR errors
        if n_cleaned.lower() in ['a', 'b', 'c', 'i', 'x', 'z', 'w', 'f', 'do', 'na', 'za', 'ul']: return False
        return True

    def is_ignorable_line(line):
        line = line.strip().lower()
        # Common receipt headers/footers/metadata
        if any(keyword in line for keyword in [
            'paragon', 'sprzedaż', 'ptu', 'suma', 'suma pln', 'razem', 'kasa', 'kasjer', 'nip',
            'sklep', 'ul.', 'data', 'godzina', 'transakcji', 'fiskalny', 'bdo',
            'dziekujemy', 'zapraszamy', 'nr sys', 'karta', 'platnicza', 'system',
            'rozliczenie płatności', 'oplata', 'rabat',  # Keep 'rabat' for now, but handle it explicitly later
            'bądz z biedronką', 'codziennie niskie ceny', 'jeronimo martins'
        ]):
            return True
        # Lines that are mostly digits, or short and meaningless
        if len(line) < 3:  # Too short to be a product name
            return True
        if re.fullmatch(r'[\d\s\W]+', line) and not re.search(r'\d+[.,]\d{2}',
                                                              line):  # Mostly numbers/symbols without a clear price
            return True
        if re.fullmatch(r'\W+', line):  # Only symbols
            return True
        return False

    def parse_product_line(line):
        """
        Parsuje linię produktu i zwraca nazwę, ilość, cenę jednostkową i całkowitą.
        Próbuje kilku wzorców w kolejności.
        """
        print(f"DEBUG: Parsing line: '{line}'")

        patterns = [
            # Główne (istniejące, które są już w kodzie)
            r'^(.+?)\s+(\d+)\s*[x×X]\s*([0-9]{1,4}[,.]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)',  #
            r'^(.+?)\s+\|?\s*(\d+)\s*[«x×X*|:]\s*([0-9]+[,.][0-9]+)\s+([0-9]+[,.][0-9]+)',  #
            r'^(.+?)\s+[ABCćĆ©]?\s*(?:\([^)]*\))?\s*(\d+)\s*[x×X]\s*([0-9]+[,.]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$',
            #
            r'^(.+?)\s*(?:\(|\|)?\s*(\d+)\s*[x×X]\s*([0-9]+[,.][0-9]+)\s+([0-9]+[,.][0-9]+)',  #
            r'^(.+?)\s+(\d+)\s*[x×X]\s*([0-9]+[,.][0-9]+)\s+([0-9]+[,.][0-9]+)',  #

            # NOWE, bardziej elastyczne wzorce:

            # 1. Nazwa, Ilość, Cena Jednostkowa, Cena Całkowita (z opcjonalną literą kategorii i/lub nawiasami)
            # Przykład: "Pomidor Maliniowy C 1.986 *6.50 12.39C"
            # Przykład: "PizzKurc Warz 140g C 2 x4,19 8,38C"
            r'^(.+?)\s+([ABCćĆ©]?)\s*(?:\([^)]*\))?\s*(\d+\s*[x×X*]?\s*[0-9]+[.,]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$',

            # 2. Nazwa, bez ilości, tylko cena całkowita (często na końcu paragonu lub dla pojedynczych pozycji)
            # Przykład: "Rabart -0,42"
            # Przykład: "satała naslowa 3.50"
            r'^(.+?)\s+([0-9]+[,.]?[0-9]{2})[ABCćĆ©]?$',

            # 3. Nazwa z jednostką wagi/objętości, ilość, cena jednostkowa, cena całkowita
            # Przykład: "MakaronySpaztle 1 x6.99 6.99C"
            # Przykład: "Filety sledz. w sosie 1 x6.89 6.89C"
            r'^(.+?\s+\d+g|\d+ml|\d+kg|\d+l)\s*([ABCćĆ©]?)\s*(\d+)\s*[x×X]\s*([0-9]+[,.]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$',

            # 4. Nazwa z ceną po spacjach, bez wyraźnej ilości/mnożnika
            # Przykład: "CH. F 1 /14.99 14.99"
            # Przykład: "Kuzkinia luz F 1.738 x8.99 15.62C" - ten jest złapany przez poprzednie, ale dla uproszczenia
            r'^(?!.*(?:x|\d+\s*[x×X]))(.+?)\s+([0-9]+[,.]?[0-9]{2})$',  # Sprawdza, czy nie ma 'x' ani liczby przed 'x'

            # 5. Fallback dla nazw produktów, gdzie cena jest oddzielona wieloma spacjami lub jest na końcu linii
            # Bardzo ogólny, powinien być na końcu.
            r'^(.+?)\s+([0-9]+[,.]?[0-9]{2})$',
            r'^(.+?)\s+\(?\s*[\w ]*\)?$'  # Istniejący fallback dla braku cen
        ]

        for pattern in patterns:
            line = fix_common_ocr_mistakes(line)
            match = re.match(pattern, line.strip())
            if match:
                groups = match.groups()
                # Logika dla każdego wzorca może być trochę inna w zależności od grup
                # Tutaj musisz dostosować, które grupy odpowiadają nazwie, ilości, cenie jednostkowej i całkowitej.
                # Przykład (dla nowego wzorca 1):
                if pattern == r'^(.+?)\s+([ABCćĆ©]?)\s*(?:\([^)]*\))?\s*(\d+\s*[x×X*]?\s*[0-9]+[.,]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$':
                    name = groups[0].strip()
                    qty_unit_price_raw = groups[2]
                    total_price = normalize_price(groups[3])

                    # Próbuj wydobyć ilość i cenę jednostkową z qty_unit_price_raw
                    qty_match = re.search(r'(\d+)\s*[x×X*]\s*([0-9]+[.,]?[0-9]*)', qty_unit_price_raw)
                    if qty_match:
                        quantity = int(qty_match.group(1))
                        unit_price = normalize_price(qty_match.group(2))
                    else:
                        quantity = None
                        unit_price = normalize_price(
                            qty_unit_price_raw)  # Jeśli brak 'x', może to być sama cena jednostkowa

                    print(
                        f"DEBUG: NEW PATTERN 1 MATCH! name='{name}', qty={quantity}, unit={unit_price}, total={total_price}")
                    return name, quantity, unit_price, total_price

                # Przykład (dla nowego wzorca 2 - tylko nazwa i cena całkowita):
                if pattern == r'^(.+?)\s+([0-9]+[,.]?[0-9]{2})[ABCćĆ©]?$':
                    name = groups[0].strip()
                    total_price = normalize_price(groups[1])
                    print(f"DEBUG: NEW PATTERN 2 MATCH! name='{name}', total={total_price}")
                    return name, None, None, total_price  # Brak ilości i ceny jednostkowej

                # Przykład (dla nowego wzorca 3 - nazwa z jednostką)
                if pattern == r'^(.+?\s+\d+g|\d+ml|\d+kg|\d+l)\s*([ABCćĆ©]?)\s*(\d+)\s*[x×X]\s*([0-9]+[,.]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$':
                    name = groups[0].strip()
                    quantity = int(groups[2])
                    unit_price = normalize_price(groups[3])
                    total_price = normalize_price(groups[4])
                    print(
                        f"DEBUG: NEW PATTERN 3 MATCH! name='{name}', qty={quantity}, unit={unit_price}, total={total_price}")
                    return name, quantity, unit_price, total_price

                # Przykład (dla nowego wzorca 4 i 5 - ogólny nazwa i cena końcowa)
                if pattern == r'^(?!.*(?:x|\d+\s*[x×X]))(.+?)\s+([0-9]+[,.]?[0-9]{2})$' or \
                        pattern == r'^(.+?)\s+([0-9]+[,.]?[0-9]{2})$':
                    name = groups[0].strip()
                    total_price = normalize_price(groups[1])
                    print(f"DEBUG: NEW PATTERN 4/5 MATCH! name='{name}', total={total_price}")
                    return name, None, None, total_price

                # Istniejąca logika dla pozostałych wzorców
                # Upewnij się, że grupy pasują do `name, quantity, unit_price, total_price`
                try:
                    name = groups[0].strip()
                    if len(groups) >= 4:  # Sprawdza, czy są wszystkie 4 grupy (nazwa, ilość, cena jedn., cena całkowita)
                        quantity = int(groups[1])
                        unit_price = normalize_price(groups[2])
                        total_price = normalize_price(groups[3])
                        print(
                            f"DEBUG: EXISTING MATCH! name='{name}', qty={quantity}, unit={unit_price}, total={total_price}")
                        return name, quantity, unit_price, total_price
                    elif len(groups) == 2:  # Jeśli tylko nazwa i cena całkowita
                        total_price = normalize_price(groups[1])
                        print(f"DEBUG: EXISTING FALLBACK MATCH (name+total)! name='{name}', total={total_price}")
                        return name, None, None, total_price
                    else:  # Jeśli tylko nazwa (np. RogalCroissant b0g)
                        print(f"DEBUG: EXISTING PARTIAL MATCH: name='{name}' (brak ilości/cen)")
                        return name, None, None, None
                except (IndexError, ValueError) as e:
                    print(f"WARNING: Błąd konwersji w istniejącym wzorcu: {e} dla linii '{line}'")
                    return None, None, None, None  # Zwraca None w przypadku błędu

        print(f"DEBUG: No match for line: '{line}'")
        # Istniejący fallback
        fallback_match = re.match(r'^(.+?)\s+([0-9]+[,.][0-9]{2})[ABCćĆ©]?$', fix_common_ocr_mistakes(line))  #
        if fallback_match:
            name = fallback_match.group(1).strip()
            total_price = normalize_price(fallback_match.group(2))
            print(f"DEBUG: FALLBACK MATCH! name='{name}', total={total_price}")
            return name, None, None, total_price
        return None, None, None, None

    parsed_data["total"] = extract_total(raw_text)
    lines = raw_text.splitlines()

    items = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or is_ignorable_line(line):  # Apply new ignorable check
            i += 1
            continue
        if not line or len(line) < 3:
            i += 1
            continue
        # Pomijamy systemowe linie
        if re.search(r'(PARAGON|SPRZEDAŻ|PTU|SUMA)', line, re.IGNORECASE):
            i += 1
            continue

        # Parsuj linię produktu
        name, quantity, unit_price, total_price = parse_product_line(line)

        if name and total_price:
            item = {
                "name": clean_name(name),
                "total_price": str(Decimal(total_price))
            }

            if quantity is not None:
                item["quantity"] = quantity
            if unit_price is not None:
                item["unit_price"] = str(Decimal(unit_price))

            # Rabat – jak wcześniej
            if i + 1 < len(lines) and i + 2 < len(lines):
                next_line = lines[i + 1].strip()
                price_line = lines[i + 2].strip()

                if "rabat" in next_line.lower() or next_line.startswith('-'):
                    clean_rabat_line = re.sub(r'[^\d\-,.]', '', next_line)
                    rabat_match = re.search(r'-([0-9]+[.,][0-9]{2})', clean_rabat_line)
                    price_match = re.search(r'^([0-9]+[.,][0-9]{2})[ABCćĆ©]?$', price_line)

                    if rabat_match and price_match:
                        rabat_amount = normalize_price(rabat_match.group(1))
                        final_price = normalize_price(price_match.group(1))

                        if rabat_amount and final_price:
                            item["discount_amount"] = str(Decimal(rabat_amount))
                            item["original_price"] = item["total_price"]
                            item["total_price"] = str(Decimal(final_price))
                            i += 3
                            items.append(item)
                            continue

            items.append(item)

        i += 1

    parsed_data["items"] = items
    return parsed_data



def process_receipt_image(receipe_id, image_path):
    from app import db
    from app.models import Receipt

    receipt = Receipt.query.get(receipe_id)
    if receipt is None:
        print(f"ERROR: Receipt {receipe_id} not found.")
        return
    try:
        receipt.status = 'Processing'
        db.session.commit()

        raw_text = run_ocr(image_path)
        receipt.raw_text = raw_text

        if raw_text.startswith("ERROR"):
            receipt.status = 'ERROR'
            receipt.processed_data = json.dumps({"error": raw_text})
        else:
            parsed_data = parse_ocr(raw_text)
            receipt.set_processed_data(parsed_data)
            receipt.status = 'Processed'
        db.session.commit()
        print(f"Processed receipt {receipe_id}. Status: {receipt.status}")

    except Exception as e:
        db.session.rollback()
        receipt.status = 'ERROR'
        receipt.processed_data = json.dumps({"error": str(e)})
        db.session.commit()
        print(f"An unexpected error occurred while processing receipt {receipe_id}: {e}")