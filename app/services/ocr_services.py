import numpy as np
import cv2
from PIL import Image
import pytesseract
import os
import re
from flask import current_app as app
import json
from decimal import Decimal, InvalidOperation # Dodano InvalidOperation


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
    Funkcja preprocessingu.
    Skupia się na kluczowych krokach: konwersji do skali szarości,
    binaryzacji i zapewnieniu właściwego formatu (czarny tekst na białym tle).
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Nie można załadować obrazu: {image_path}")

        # Krok 1: Konwersja do skali szarości
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Automatyczna korekcja orientacji za pomocą Tesseract OSD
        try:
            osd_data = pytesseract.image_to_osd(gray)
            rotation_angle = 0

            for line in osd_data.split('\n'):
                if 'Rotate:' in line:
                    rotation_angle = int(line.split(':')[1].strip())
                    break

            if rotation_angle != 0:
                (h, w) = gray.shape[:2]
                center = (w // 2, h // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)
                gray = cv2.warpAffine(gray, rotation_matrix, (w, h),
                                      flags=cv2.INTER_CUBIC,
                                      borderMode=cv2.BORDER_REPLICATE)
                print(f"DEBUG: Skorygowano orientację obrazu o {rotation_angle} stopni.")
        except Exception as e:
            print(f"DEBUG: Tesseract OSD nie zadziałał, kontynuuję bez korekcji orientacji: {e}")

        # Krok 3: Korekcja przekrzywienia (Deskewing)
        try:
            coords = np.column_stack(np.where(gray > 0))
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            if 1 < abs(angle) < 45:
                (h, w) = gray.shape[:2]
                center = (w // 2, h // 2)
                m = cv2.getRotationMatrix2D(center, angle, 1.0)
                gray = cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                print(f"DEBUG: Skorygowano przekrzywienie obrazu o {angle:.2f} stopni.")
        except Exception as e:
            print(f"WARNING: Nie udało się skorygować przekrzywienia: {e}")

        # Krok 4: Binaryzacja z metodą Otsu
        thresh_value, thresh_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        print(f"DEBUG: Użyto progu Otsu o wartości: {thresh_value}")

        # Krok 5: Zapewnienie, że tekst jest czarny na białym tle
        if np.mean(thresh_image) < 128:
            print("DEBUG: Wykryto biały tekst na czarnym tle. Inwertuję obraz.")
            thresh_image = cv2.bitwise_not(thresh_image)

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

    original_tmpdir = os.environ.get('TMPDIR')
    original_temp = os.environ.get('TEMP')
    original_tmp = os.environ.get('TMP')

    tesseract_temp_dir = app.config.get('TESSERACT_TEMP_DIR')
    if not tesseract_temp_dir:
        return "ERROR: Tesseract temporary directory not configured."

    os.makedirs(tesseract_temp_dir, exist_ok=True)

    try:
        os.environ['TMPDIR'] = tesseract_temp_dir
        os.environ['TEMP'] = tesseract_temp_dir
        os.environ['TMP'] = tesseract_temp_dir

        preprocessed_image = preprocess_image(image_path)
        if preprocessed_image is None:
            return "ERROR: Image preprocessing failed."

        configs = [
            '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĄĆĘŁŃÓŚŹŻąćęłńóśźż.,:-+/()%|[]{}',
            '--oem 3 --psm 4',
            '--oem 3 --psm 6',
        ]

        best_result = ""
        best_confidence = 0

        for config in configs:
            try:
                result = pytesseract.image_to_string(preprocessed_image, lang='pol', config=config)
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
    """
    Parsuje surowy tekst z OCR, aby wyodrębnić nazwy produktów i ceny.
    Zwraca słownik z kluczem "items", gdzie "total_price" jest stringiem.
    """
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

        if re.fullmatch(r'\d{3}', s):
            s = f"{s[:-2]}.{s[-2:]}"

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
            except InvalidOperation: # Użyj InvalidOperation
                pass
        return None

    def clean_name(n):
        n = re.sub(r'[|()©*„”\'`~]', '', n)
        n = re.sub(r'\s+[ABCćĆ©]$', '', n)
        n = re.sub(r'\s+\d+x\d+[.,]\d{2}', '', n)
        n = re.sub(r'\s+\d+[.,]\d{2}$', '', n)
        n = re.sub(r'\s+', ' ', n).strip()
        n = re.sub(r'\s+\d{4,}$', '', n)
        return n

    def is_valid_name(n):
        if not n:
            return False
        n_cleaned = n.strip()
        if len(n_cleaned) < 4:
            return False
        letters = len(re.findall(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', n_cleaned))
        digits = len(re.findall(r'\d', n_cleaned))
        symbols = len(re.findall(r'[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\d\s]', n_cleaned))

        if letters == 0 and digits > 0: return False
        if letters < digits / 2 : return False
        if letters == 0 and symbols > 0: return False
        if re.match(r'^\d', n_cleaned): return False

        if n_cleaned.lower() in ['a', 'b', 'c', 'i', 'x', 'z', 'w', 'f', 'do', 'na', 'za', 'ul', 'z', 'nr', 'vat', 'pt', 'o', 'r', 'u', 's', 'l', 'g', 'e', 'm', 'p', 'b', 'd', 'k']: return False
        return True

    def is_ignorable_line(line):
        line = line.strip().lower()
        if any(keyword in line for keyword in [
            'paragon', 'sprzedaż','sprzedaz','numer', 'numor', 'ptu', 'suma', 'suma pln', 'razem', 'kasa', 'kasjer', 'nip',
            'sklep', 'ul.', 'data', 'godzina', 'transakcji', 'fiskalny', 'bdo',
            'dziekujemy', 'zapraszamy', 'nr sys', 'karta', 'platnicza', 'system',
            'rozliczenie płatności', 'oplata', 'opodatkowana',
            'bądz z biedronką', 'codziennie niskie ceny', 'jeronimo martins', 'o.', 'r.', 'nr', 'vat', 'pt'
        ]):
            return True
        if len(line) < 3:
            return True
        if re.fullmatch(r'[\d\s\W]+', line) and not re.search(r'\d+[.,]\d{2}',
                                                              line):
            return True
        if re.fullmatch(r'\W+', line):
            return True
        return False

    def parse_product_line(line):
        print(f"DEBUG: Parsing line: '{line}'")

        patterns = [
            r'^(.+?)\s+([ABCćĆ©]?)\s*(?:\([^)]*\))?\s*(\d+[.,]?\d*\s*[x×X*]?\s*[0-9]+[.,]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$',
            r'^(.+?(?:\s+\d+g|\d+ml|\d+kg|\d+l)?)\s*(\d+)\s*[x×X*]\s*([0-9]+[,.]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$',
            r'^(?!.*\s(?:\d+\s*[x×X]))(.+?)\s+([0-9]+[,.]?[0-9]{2})[ABCćĆ©]?$',
            r'^(.+?)\s+([0-9]+[,.]?[0-9]{2})$',
        ]

        for pattern in patterns:
            line = fix_common_ocr_mistakes(line)
            match = re.match(pattern, line.strip())
            if match:
                groups = match.groups()

                if pattern == r'^(.+?)\s+([ABCćĆ©]?)\s*(?:\([^)]*\))?\s*(\d+[.,]?\d*\s*[x×X*]?\s*[0-9]+[.,]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$':
                    name = groups[0].strip()
                    qty_unit_price_raw = groups[2]
                    total_price = normalize_price(groups[3])

                    qty_match = re.search(r'(\d+[.,]?\d*)\s*[x×X*]\s*([0-9]+[.,]?[0-9]*)', qty_unit_price_raw)
                    if qty_match:
                        try:
                            quantity = float(qty_match.group(1).replace(',', '.'))
                            unit_price = normalize_price(qty_match.group(2))
                        except ValueError:
                            quantity = None
                            unit_price = None
                    else:
                        quantity = None
                        unit_price = None

                    if is_valid_name(name) and total_price:
                        print(f"DEBUG: NEW PATTERN 1 MATCH! name='{name}', qty={quantity}, unit={unit_price}, total={total_price}")
                        return name, quantity, unit_price, total_price
                    else:
                        print(f"DEBUG: NEW PATTERN 1 matched but not valid item: name='{name}', total={total_price}")
                        continue

                elif pattern == r'^(.+?(?:\s+\d+g|\d+ml|\d+kg|\d+l)?)\s*(\d+)\s*[x×X*]\s*([0-9]+[,.]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$':
                    name = groups[0].strip()
                    try:
                        quantity = int(groups[1])
                    except ValueError:
                        quantity = None
                    unit_price = normalize_price(groups[2])
                    total_price = normalize_price(groups[3])
                    if is_valid_name(name) and total_price:
                        print(f"DEBUG: NEW PATTERN 2 MATCH! name='{name}', qty={quantity}, unit={unit_price}, total={total_price}")
                        return name, quantity, unit_price, total_price
                    else:
                        print(f"DEBUG: NEW PATTERN 2 matched but not valid item: name='{name}', total={total_price}")
                        continue

                elif pattern == r'^(?!.*\s(?:\d+\s*[x×X]))(.+?)\s+([0-9]+[,.]?[0-9]{2})[ABCćĆ©]?$':
                    name = groups[0].strip()
                    total_price = normalize_price(groups[1])
                    if is_valid_name(name) and total_price:
                        print(f"DEBUG: NEW PATTERN 3 MATCH! name='{name}', total={total_price}")
                        return name, None, None, total_price
                    else:
                        print(f"DEBUG: NEW PATTERN 3 matched but not valid item: name='{name}', total={total_price}")
                        continue

                elif pattern == r'^(.+?)\s+([0-9]+[,.]?[0-9]{2})$':
                    name = groups[0].strip()
                    total_price = normalize_price(groups[1])
                    if is_valid_name(name) and total_price:
                        print(f"DEBUG: NEW PATTERN 4 MATCH! name='{name}', total={total_price}")
                        return name, None, None, total_price
                    else:
                        print(f"DEBUG: NEW PATTERN 4 matched but not valid item: name='{name}', total={total_price}")
                        continue

        print(f"DEBUG: No match for line: '{line}'")
        return None, None, None, None

    parsed_data["total"] = extract_total(raw_text)
    lines = raw_text.splitlines()

    items = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or is_ignorable_line(line):
            i += 1
            continue

        name, quantity, unit_price, total_price = parse_product_line(line)
        if total_price is not None:
            try:
                if Decimal(total_price) > Decimal('10000.00'):
                    print(f"WARNING: Skipping item '{name}' with unusually high total price: {total_price}")
                    i += 1
                    continue
            except InvalidOperation:
                print(f"WARNING: Could not convert total_price '{total_price}' to Decimal for validation. Skipping.")
                i += 1
                continue


        if name and total_price:
            item = {
                "name": clean_name(name),
                "total_price": str(Decimal(total_price)) # Upewnij się, że jest to string
            }

            if quantity is not None:
                item["quantity"] = quantity
            if unit_price is not None:
                item["unit_price"] = str(Decimal(unit_price)) # Upewnij się, że jest to string

            # Rabat – jak wcześniej
            if i + 2 < len(lines):
                next_line = lines[i + 1].strip()
                potential_price_line = lines[i + 2].strip()

                rabat_match = re.search(r'rabat|zniżka|bon', next_line, re.IGNORECASE)
                negative_price_match_in_next = re.search(r'-([0-9]+[.,][0-9]{2})', next_line)
                final_price_match_in_potential_price_line = re.search(r'^([0-9]+[.,][0-9]{2})[ABCćĆ©]?$', potential_price_line)

                if (rabat_match or negative_price_match_in_next) and final_price_match_in_potential_price_line:
                    rabat_amount_str = None
                    if negative_price_match_in_next:
                        rabat_amount_str = normalize_price(negative_price_match_in_next.group(1))
                    elif rabat_match:
                        rabat_amount_in_rabat_line = re.search(r'([0-9]+[.,][0-9]{2})', next_line)
                        if rabat_amount_in_rabat_line:
                            rabat_amount_str = normalize_price(rabat_amount_in_rabat_line.group(1))

                    final_price_str = normalize_price(final_price_match_in_potential_price_line.group(1))

                    if rabat_amount_str and final_price_str:
                        try:
                            discount_decimal = Decimal(rabat_amount_str)
                            final_decimal = Decimal(final_price_str)
                            original_decimal = Decimal(item["total_price"])

                            if abs((original_decimal - discount_decimal) - final_decimal) < Decimal('0.05'):
                                item["discount_amount"] = str(discount_decimal) # Upewnij się, że jest to string
                                item["original_price"] = item["total_price"]
                                item["total_price"] = str(final_decimal) # Upewnij się, że jest to string
                                i += 2
                                items.append(item)
                                i += 1
                                continue
                        except InvalidOperation as e: # Catch InvalidOperation here too
                            print(f"Error processing discount (InvalidOperation): {e}")
                        except Exception as e:
                            print(f"Error processing discount: {e}")

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

