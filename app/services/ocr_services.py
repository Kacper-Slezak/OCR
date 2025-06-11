from decimal import Decimal

import cv2
from PIL import Image
import pytesseract
import os
import re
from flask import current_app as app
import json


def set_tesseact_path():
    tesseract_path = app.config.get('TESSERACT_PATH')
    if tesseract_path and os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    else:
        print(f'WARING: No tesseract path found at {tesseract_path}. Configure .env variables first.')

def preprocess_image(image_path):
    """
    Preprocess the image for OCR.
    Gray scale
    Delete noise
    :param image_path: path to image
    :return: preprocessed image
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"{image_path} is not a valid image.")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        return Image.fromarray(thresh)
    except Exception as e:
        print(f"Błąd podczas przetwarzania obrazu '{image_path}': {e}")
        try:
            return Image.open(image_path)
        except Exception as img_e:
            print(f"Nie udało się wczytać oryginalnego obrazu: {img_e}")
            return None

def run_ocr(image_path):
    """
    OCR the image and return the result.
    :param image_path:
    :return:
    """
    set_tesseact_path()
    try:
        preprocessed_image = preprocess_image(image_path)
        if preprocessed_image is None:
            return "ERROR: Image preprocessing failed."
        raw_text = pytesseract.image_to_string(preprocessed_image, lang='pl')
        return raw_text
    except pytesseract.TesseractNotFoundError:
        return "ERROR: Tesseract not found."
    except Exception as e:
        return f"OCR failed e."

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

        if "ERROR" in raw_text:
            receipt.status = 'ERROR'
            receipt.processed_data = json.dumps({"error": raw_text})
        else:
            parsed_data = parse_ocr(raw_text)
            receipt.set_parsed_data(parsed_data)
            receipt.status = 'Processed'
        db.session.commit()
        print(f"Processed receipt {receipe_id}. Status: {receipt.status}")

    except Exception as e:
        db.session.rollback()
        receipt.status = 'ERROR'
        receipt.processed_data = json.dumps({"error": str(e)})
        db.session.commit()
        print(f"An unexpected error occurred while processing receipt {receipe_id}: {e}")

