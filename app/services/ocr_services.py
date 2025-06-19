from decimal import Decimal
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
    print(f"DEBUG: TESSERACT_PATH z config.py: '{tesseract_path}'") # Dodana linia
    if tesseract_path and os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        print(f"DEBUG: Ustawiono pytesseract.pytesseract.tesseract_cmd na: '{tesseract_path}'") # Dodana linia
    else:
        print(f'WARING: No tesseract path found at {tesseract_path}. Configure .env variables first.')
        print(f"DEBUG: Czy ścieżka istnieje według os.path.exists? {os.path.exists(tesseract_path)}") # Dodana linia
        print(f"DEBUG: Typ tesseract_path: {type(tesseract_path)}")

def preprocess_image(image_path):
    """
    Preprocess the image for OCR.
    Includes advanced denoising, contrast enhancement, sharpening, and adaptive thresholding.
    :param image_path: path to image
    :return: preprocessed image
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"{image_path} is not a valid image.")

        gray = cv2.cvtColor(image, cv2.BGR2GRAY)

        # 1. Denoising: Non-local Means Denoising
        # This is excellent for removing various types of noise while preserving text edges.
        # h: filter strength (higher for more aggressive denoising), templateWindowSize & searchWindowSize for local area
        denoised = cv2.fastNlMeansDenoising(gray, None, h=30, templateWindowSize=7, searchWindowSize=21)

        # 2. Contrast Enhancement: CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # Improves local contrast, making text pop out from the background, especially in unevenly lit areas.
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)) # Adjusted clipLimit slightly
        enhanced = clahe.apply(denoised)

        # 3. Sharpening: Enhance text edges using an unsharp mask
        # This technique enhances edges without increasing noise as much as a simple sharpening kernel.
        # First, blur the image
        blurred = cv2.GaussianBlur(enhanced, (0,0), 3) # Gaussian blur with sigmaX=3
        # Then, subtract the blurred image from the original (scaled)
        sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0) # Adjust alpha (1.5) and beta (-0.5) for intensity

        # 4. Remove small specks (noise) - erosion followed by dilation (Opening)
        # This helps in removing tiny dots or disconnected components that aren't part of the text.
        kernel_open = np.ones((1,1), np.uint8) # A small kernel is usually sufficient for text noise
        cleaned = cv2.morphologyEx(sharpened, cv2.MORPH_OPEN, kernel_open)

        # 5. Binarization: Adaptive Thresholding
        # Using ADAPTIVE_THRESH_GAUSSIAN_C is robust for receipts with varied lighting.
        # block size: 31 (must be odd), C: 2 (constant subtracted from mean/weighted mean)
        thresh = cv2.adaptiveThreshold(
            cleaned, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 2
        )

        return Image.fromarray(thresh)
    except Exception as e:
        print(f"Error during image processing for '{image_path}': {e}")
        try:
            # Fallback to opening the original image if preprocessing fails
            return Image.open(image_path)
        except Exception as img_e:
            print(f"Could not load original image: {img_e}")
            return None

def run_ocr(image_path):
    """
    OCR the image and return the result.
    :param image_path:
    :return:
    """
    set_tesseact_path()

    # Zmienne do przechowywania oryginalnych wartości zmiennych środowiskowych
    original_tmpdir = os.environ.get('TMPDIR')
    original_temp = os.environ.get('TEMP')
    original_tmp = os.environ.get('TMP')

    tesseract_temp_dir = app.config.get('TESSERACT_TEMP_DIR')
    if not tesseract_temp_dir:
        return "ERROR: Tesseract temporary directory not configured."

    os.makedirs(tesseract_temp_dir, exist_ok=True) # Upewnij się, że katalog istnieje

    try:
        # Tymczasowo ustawiamy zmienne środowiskowe, które Tesseract może używać
        # dla plików tymczasowych. Robimy to dla os.environ globalnie,
        # ponieważ argument 'env' nie jest obsługiwany przez Twoją wersję pytesseract.
        os.environ['TMPDIR'] = tesseract_temp_dir
        os.environ['TEMP'] = tesseract_temp_dir
        os.environ['TMP'] = tesseract_temp_dir

        preprocessed_image = preprocess_image(image_path)
        if preprocessed_image is None:
            return "ERROR: Image preprocessing failed."

        # Ustawienie opcji konfiguracji dla Tesseracta
        tess_config = '--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(preprocessed_image, lang='pol', config=tess_config)

        return raw_text
    except pytesseract.TesseractNotFoundError:
        return "ERROR: Tesseract not found. Make sure it's installed and path is configured."
    except Exception as e:
        # Poprawiony komunikat o błędzie, aby był bardziej pomocny
        return f"OCR failed: {e}"
    finally:
        # ZAWSZE przywracamy oryginalne zmienne środowiskowe, aby nie wpływać na inne części systemu/aplikacji
        if original_tmpdir is not None:
            os.environ['TMPDIR'] = original_tmpdir
        else:
            if 'TMPDIR' in os.environ:
                del os.environ['TMPDIR']

        if original_temp is not None:
            os.environ['TEMP'] = original_temp
        else:
            if 'TEMP' in os.environ:
                del os.environ['TEMP']

        if original_tmp is not None:
            os.environ['TMP'] = original_tmp
        else:
            if 'TMP' in os.environ:
                del os.environ['TMP']

def parse_ocr(raw_text):
    """
    Parse the text and return the result.
    :param raw_text:
    :return parsed text:
    """
    parsed_data = {
        "items": [],
        "total": None,
        "date": None,
    }

    lines = raw_text.split('\n')

    item_patterns = [
        re.compile(r'(.+?)\s+([\d,\.]+\d{2})\s*([A-Za-z]\b)?$', re.IGNORECASE),
        re.compile(r'(.+?)\s+(\d+)\s*x\s*([\d,\.]+\d{2})\s+([\d,\.]+\d{2})\s*([A-Za-z]\b)?$', re.IGNORECASE),
        re.compile(r'(\d+)\s*x\s*(.+?)\s+([\d,\.]+\d{2})\s*([A-Za-z]\b)?$', re.IGNORECASE),
        re.compile(r'(.+?)\s+(\d+)\s+([\d,\.]+\d{2})\s*([A-Za-z]\b)?$', re.IGNORECASE),
        re.compile(r'([\d,\.]+\d{2})\s+(.+?)$', re.IGNORECASE),
    ]
    ignore_patterns = [
        re.compile(r'^(PARAGON FISKALNY|SPRZEDAŻ OPODATK\.|PTU|SUMA|TOTAL|RAZEM|GOTÓWKA|KARTA|DO ZAPŁATY|KWOTA|VAT)$',
                   re.IGNORECASE),
        re.compile(r'^\d{2}[-./]\d{2}[-./]\d{2,4}$'),
        re.compile(r'^(\d+\s*x\s*\d+\s*x\s*\d+\s*=\s*\d+)?$', re.IGNORECASE),
        re.compile(r'^[A-Z]\s*\d+\.?\d*$', re.IGNORECASE)
    ]

    for line_index, line in enumerate(lines):
        original_line = line.strip()
        line_upper = original_line.upper()

        if not original_line:
            continue

        should_ignore = False
        for pattern in ignore_patterns:
            if pattern.search(line_upper):
                should_ignore = True
                break
        if should_ignore:
            continue

        found_match = False
        for pattern in item_patterns:
            match = pattern.search(original_line)
            if match:
                try:
                    item_data = {}
                    if pattern == item_patterns[0]:
                        item_data["name"] = match.group(1).strip()
                        item_data["price"] = str(Decimal(match.group(2).replace(',', '.')))
                    elif pattern == item_patterns[1]:
                        item_data["name"] = match.group(1).strip()
                        item_data["quantity"] = int(match.group(2))
                        item_data["price_per_unit"] = str(Decimal(match.group(3).replace(',', '.')))
                        item_data["total_price"] = str(Decimal(match.group(4).replace(',', '.')))
                    elif pattern == item_patterns[2]:
                        item_data["quantity"] = int(match.group(1))
                        item_data["name"] = match.group(2).strip()
                        item_data["total_price"] = str(Decimal(match.group(3).replace(',', '.')))

                    elif pattern == item_patterns[3]:
                        item_data["name"] = match.group(1).strip()
                        item_data["quantity"] = int(match.group(2))
                        item_data["total_price"] = str(Decimal(match.group(3).replace(',', '.')))

                    elif pattern == item_patterns[4]:
                        item_data["total_price"] = str(Decimal(match.group(1).replace(',', '.')))
                        item_data["name"] = match.group(2).strip()

                    parsed_data["items"].append(item_data)
                    found_match = True
                    break
                except Exception as e:
                    pass
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

        if raw_text.startswith("ERROR"): # Sprawdzamy czy komunikat zaczyna się od "ERROR"
            receipt.status = 'ERROR'
            receipt.processed_data = json.dumps({"error": raw_text})
        else:
            parsed_data = parse_ocr(raw_text)
            receipt.set_processed_data(parsed_data) # Pamiętaj, żeby to było poprawione
            receipt.status = 'Processed'
        db.session.commit()
        print(f"Processed receipt {receipe_id}. Status: {receipt.status}")

    except Exception as e:
        db.session.rollback()
        receipt.status = 'ERROR'
        receipt.processed_data = json.dumps({"error": str(e)})
        db.session.commit()
        print(f"An unexpected error occurred while processing receipt {receipe_id}: {e}")
