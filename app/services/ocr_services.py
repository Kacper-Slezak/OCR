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


def clean_ocr_text(text):
    """
    Clean and normalize OCR text to fix common recognition errors.
    """
    # Character substitutions for common OCR errors
    substitutions = {
        'ĄĄ': 'AA',
        'ęę': 'ee',
        'ŻŻ': 'ZZ',
        'ŹŹ': 'ZZ',
        'ĆĆ': 'CC',
        'ŁŁ': 'LL',
        'ŃŃ': 'NN',
        'ÓÓ': 'OO',
        'ŚŚ': 'SS',
        '|': 'I',
        '!': 'I',
        'O': '0',  # Only in price contexts
        'S': '5',  # Only in price contexts
        'l': '1',  # Only in price contexts
        'I': '1',  # Only in price contexts
        'b': '6',  # Common in OCR
        'G': '6',  # Common in OCR
        'A': '4',  # In some contexts
        'T': '7',  # In some contexts
        'Z': '2',  # In some contexts
        'B': '8',  # In some contexts
    }

    # Apply substitutions
    cleaned_text = text
    for old, new in substitutions.items():
        cleaned_text = cleaned_text.replace(old, new)

    # Fix common Polish OCR errors
    polish_fixes = {
        'Czek': 'Czek',
        'Gorzowska': 'Gorzowska',
        'Poma': 'Poma',
        'Melt': 'Melt',
        'Jaja': 'Jaja',
        'Kyb': 'Kyb',
        'Piuo': 'Piwo',
        'Budueiser': 'Budweiser',
        'Salankrakiędkix': 'Salami Krakowski',
        'Schab': 'Schab',
        'Szynka': 'Szynka',
        'Herbata': 'Herbata',
        'Jutrzeni': 'Jutrzenki',
        'Ketchup': 'Ketchup',
        'PikKot': 'Pikant',
        'Tost': 'Tost',
        'Pszenny': 'Pszenny',
        'Pierniki': 'Pierniki',
        'Wafki': 'Wafle',
        'Orzech': 'Orzech',
        'Limonka': 'Limonka',
        'Kostki': 'Kostki',
        'Lodu': 'Lodu',
        'Bułka': 'Bułka',
        'Codzienna': 'Codzienna',
    }

    for old, new in polish_fixes.items():
        cleaned_text = re.sub(re.escape(old), new, cleaned_text, flags=re.IGNORECASE)

    return cleaned_text


def parse_ocr(raw_text):
    """
    Enhanced OCR parsing with better pattern recognition.
    """
    parsed_data = {
        "items": [],
        "total": None,
        "date": None,
        "store": None,
        "raw_text": raw_text
    }

    # Clean the text first
    cleaned_text = clean_ocr_text(raw_text)
    lines = cleaned_text.split('\n')

    # Enhanced regex patterns
    item_patterns = [
        # Pattern 1: Product name + quantity + unit price + total price
        re.compile(
            r'^(.+?)\s+(\d+)\s*[x×]\s*([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s*([A-Z])?$',
            re.IGNORECASE),

        # Pattern 2: Product name + price + tax category
        re.compile(r'^(.+?)\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s*([A-Z])?$', re.IGNORECASE),

        # Pattern 3: Product name with quantity in parentheses + price
        re.compile(
            r'^(.+?)\s*\(\s*(\d+)\s*[x×]\s*([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s*\)\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s*([A-Z])?$',
            re.IGNORECASE),

        # Pattern 4: Quantity + product name + price
        re.compile(r'^(\d+)\s*[x×]\s*(.+?)\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s*([A-Z])?$', re.IGNORECASE),

        # Pattern 5: Product name + multiple prices (unit and total)
        re.compile(r'^(.+?)\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s*([A-Z])?$',
                   re.IGNORECASE),
    ]

    # Enhanced ignore patterns
    ignore_patterns = [
        re.compile(
            r'^(BIEDRONKA|PARAGON\s*FISKALNY|SPRZEDAŻ\s*OPODATK|PTU|SUMA|TOTAL|RAZEM|GOTÓWKA|KARTA|SKLEP|JERONIMO|MARTINS|POLSKA|NIP|NUMER|TRANSAKCJI|KASY|KASJERA|DZIEKUJEMY|ZAPRASZAMY|RABAT).*$',
            re.IGNORECASE),
        re.compile(r'^\d{2}[-./]\d{2}[-./]\d{2,4}.*$'),  # Dates
        re.compile(r'^\d{4,}.*$'),  # Long numbers
        re.compile(r'^[A-Z0-9]{10,}.*$'),  # System codes
        re.compile(r'^[A-Z]\s*\d+[.,]?\d*%?$'),  # Tax codes
        re.compile(r'^\d{2}-\d{3}.*$'),  # Postal codes
        re.compile(r'^UL\..*$', re.IGNORECASE),  # Addresses
        re.compile(r'^[\s\d\-,.©cC]+$'),  # Only symbols and numbers
        re.compile(r'^[A-Za-z]{1,2}$'),  # Single letters
        re.compile(r'^[.,\-\s]+$'),  # Only punctuation
        re.compile(r'^SPRZEDA[ŻZ]?\s*OPODATKOW.*$', re.IGNORECASE),
        re.compile(r'^PTU\s*[A-Z].*$', re.IGNORECASE),
        re.compile(r'^SUMA\s*PLN.*$', re.IGNORECASE),
    ]

    def normalize_price(price_str):
        """Enhanced price normalization"""
        if not price_str:
            return None

        # Remove spaces and normalize
        price_str = price_str.replace(' ', '').replace(',', '.')

        # Handle different price formats
        if re.match(r'^\d+\.\d{2}$', price_str):
            return price_str
        elif re.match(r'^\d+\.\d{1}$', price_str):
            return price_str + '0'
        elif re.match(r'^\d+$', price_str):
            return price_str + '.00'
        elif re.match(r'^\d+\.\d{3,}$', price_str):
            # Probably missing decimal separator
            return price_str[:-2] + '.' + price_str[-2:]

        # Try to extract valid price
        numbers = re.findall(r'\d+', price_str)
        if len(numbers) >= 2:
            return f"{numbers[0]}.{numbers[1][:2].zfill(2)}"
        elif len(numbers) == 1:
            num = numbers[0]
            if len(num) <= 2:
                return f"0.{num.zfill(2)}"
            else:
                return f"{num[:-2]}.{num[-2:]}"

        return price_str

    def extract_date(text):
        """Extract date from text"""
        date_patterns = [
            re.compile(r'(\d{4})-(\d{2})-(\d{2})', re.IGNORECASE),
            re.compile(r'(\d{2})/(\d{2})/(\d{4})', re.IGNORECASE),
            re.compile(r'(\d{2})\.(\d{2})\.(\d{4})', re.IGNORECASE),
            re.compile(r'(\d{2})-(\d{2})-(\d{4})', re.IGNORECASE),
        ]

        for pattern in date_patterns:
            match = pattern.search(text)
            if match:
                if len(match.group(1)) == 4:  # Year first
                    return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
                else:  # Day first
                    return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
        return None

    def extract_total(text):
        """Extract total amount from text"""
        total_patterns = [
            re.compile(r'SUMA\s+PLN\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})', re.IGNORECASE),
            re.compile(r'RAZEM\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})', re.IGNORECASE),
            re.compile(r'TOTAL\s+([0-9]{1,3}[.,]?\s*[0-9]{1,2})', re.IGNORECASE),
            re.compile(r'([0-9]{1,3}[.,]?\s*[0-9]{1,2})\s*$', re.MULTILINE),  # End of line price
        ]

        for pattern in total_patterns:
            match = pattern.search(text)
            if match:
                cleaned_price = normalize_price(match.group(1))
                if cleaned_price:
                    try:
                        return str(Decimal(cleaned_price))
                    except:
                        continue
        return None

    def is_valid_product_name(name):
        """Check if product name is valid"""
        if not name or len(name.strip()) < 2:
            return False

        name = name.strip()

        # Must contain at least one letter
        if not re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', name):
            return False

        # Reject if mostly numbers
        if len(re.sub(r'[^0-9]', '', name)) > len(name) * 0.7:
            return False

        # Reject obvious garbage
        garbage_patterns = [
            r'^[.,\-\s]+$',
            r'^\d+:\s*$',
            r'^[A-Z]{1,2}$',
            r'^[b-z]{1,2}$',
        ]

        for pattern in garbage_patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return False

        return True

    # Extract metadata
    parsed_data["date"] = extract_date(raw_text)
    parsed_data["total"] = extract_total(raw_text)

    # Extract store info
    if "BIEDRONKA" in raw_text.upper():
        parsed_data["store"] = "Biedronka"

    # Parse items
    for line in lines:
        original_line = line.strip()

        if not original_line or len(original_line) < 3:
            continue

        # Check ignore patterns
        should_ignore = False
        for pattern in ignore_patterns:
            if pattern.search(original_line):
                should_ignore = True
                break

        if should_ignore:
            continue

        # Try to match item patterns
        for pattern_index, pattern in enumerate(item_patterns):
            match = pattern.search(original_line)
            if match:
                try:
                    item_data = {}

                    if pattern_index == 0:  # Product + quantity + unit price + total
                        product_name = match.group(1).strip()
                        quantity = int(match.group(2))
                        unit_price = normalize_price(match.group(3))
                        total_price = normalize_price(match.group(4))
                        tax_category = match.group(5) if len(match.groups()) > 4 else None

                        if is_valid_product_name(product_name):
                            item_data["name"] = product_name
                            item_data["quantity"] = quantity
                            if unit_price:
                                item_data["unit_price"] = str(Decimal(unit_price))
                            if total_price:
                                item_data["total_price"] = str(Decimal(total_price))
                            if tax_category:
                                item_data["tax_category"] = tax_category

                    elif pattern_index == 1:  # Product + price + tax
                        product_name = match.group(1).strip()
                        price = normalize_price(match.group(2))
                        tax_category = match.group(3) if len(match.groups()) > 2 else None

                        if is_valid_product_name(product_name):
                            item_data["name"] = product_name
                            if price:
                                item_data["price"] = str(Decimal(price))
                            if tax_category:
                                item_data["tax_category"] = tax_category

                    # Similar processing for other patterns...

                    # Add item if valid
                    if item_data.get("name") and (item_data.get("price") or item_data.get("total_price")):
                        parsed_data["items"].append(item_data)
                        break

                except (ValueError, IndexError, Exception) as e:
                    continue

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