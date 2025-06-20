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
    Enhanced image preprocessing for better OCR results.
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"{image_path} is not a valid image.")

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Apply bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)

        # Apply CLAHE for better contrast
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Apply Gaussian blur and unsharp mask for sharpening
        gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
        sharpened = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)

        # Morphological operations to clean up small artifacts
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(sharpened, cv2.MORPH_CLOSE, kernel)

        # Adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            cleaned, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        return Image.fromarray(thresh)

    except Exception as e:
        print(f"Error during image processing for '{image_path}': {e}")
        try:
            return Image.open(image_path)
        except Exception as img_e:
            print(f"Could not load original image: {img_e}")
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

    def normalize_price(price_str):
        if not price_str:
            return None
        s = price_str.strip().replace(',', '.')
        # Usuń litery A, B, C na końcu
        s = re.sub(r'[ABCćĆ©]$', '', s)
        if re.fullmatch(r'\d{3}', s):
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
        n = re.sub(r'[|()©*]', '', n)
        n = re.sub(r'\s+', ' ', n).strip()
        return re.sub(r'\s+\d{4,}$', '', n)

    def is_valid_name(n):
        if re.match(r'^\d', n): return False
        letters = len(re.findall(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', n))
        digits = len(re.findall(r'\d', n))
        return letters >= digits and len(n.strip()) >= 3

    def parse_product_line(line):
        """Parsuje linię produktu i zwraca nazwę, ilość, cenę jednostkową i całkowitą"""
        print(f"DEBUG: Parsing line: '{line}'")

        # Wzorzec: wszystko do momentu gdy znajdziemy cyfra+x cyfra,cyfra cyfra,cyfra+litera
        # Przykład: "OrzechZi emPapryk240g C 1x 6,29 6,29C"
        pattern = r'^(.+?)\s+[ABCćĆ©]?\s*(?:\([^)]*\))?\s*(\d+)x\s+([0-9]+[,.]?[0-9]*)\s+([0-9]+[,.]?[0-9]*)[ABCćĆ©]?$'

        match = re.match(pattern, line.strip())
        if match:
            name = match.group(1).strip()
            quantity = int(match.group(2))
            unit_price = normalize_price(match.group(3))
            total_price = normalize_price(match.group(4))

            print(f"DEBUG: Found - name: '{name}', qty: {quantity}, unit: {unit_price}, total: {total_price}")
            return name, quantity, unit_price, total_price

        print(f"DEBUG: No match for line: '{line}'")
        return None, None, None, None

    parsed_data["total"] = extract_total(raw_text)
    lines = raw_text.splitlines()

    items = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or len(line) < 3:
            i += 1
            continue

        # Pomijamy systemowe linie
        if re.search(r'(PARAGON|SPRZEDAŻ|PTU|SUMA)', line, re.IGNORECASE):
            i += 1
            continue

        # Parsuj linię produktu
        name, quantity, unit_price, total_price = parse_product_line(line)

        if name and quantity and unit_price and total_price:
            name = clean_name(name)

            if is_valid_name(name):
                item = {
                    "name": name,
                    "quantity": quantity,
                    "unit_price": str(Decimal(unit_price)),
                    "total_price": str(Decimal(total_price))
                }

                # Sprawdź rabat w następnych liniach
                if i + 1 < len(lines) and i + 2 < len(lines):
                    next_line = lines[i + 1].strip()
                    price_line = lines[i + 2].strip()

                    # Sprawdź czy to rabat
                    if "rabat" in next_line.lower() or next_line.startswith('-'):
                        rabat_match = re.search(r'-([0-9]+[.,][0-9]{2})', next_line)
                        price_match = re.search(r'^([0-9]+[.,][0-9]{2})[ABCćĆ©]?$', price_line)

                        if rabat_match and price_match:
                            rabat_amount = normalize_price(rabat_match.group(1))
                            final_price = normalize_price(price_match.group(1))

                            if rabat_amount and final_price:
                                item["discount_amount"] = str(Decimal(rabat_amount))
                                item["original_price"] = item["total_price"]
                                item["total_price"] = str(Decimal(final_price))
                                i += 3  # Przeskocz produkt, rabat, cenę końcową
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