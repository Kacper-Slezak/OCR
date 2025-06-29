import re
from decimal import Decimal

def normalize_text(text):
    """Normalizuje tekst do porównań (małe litery, usuwanie znaków specjalnych)."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r'[^a-z0-9\s]', '', text.lower())
    return ' '.join(text.split())


def generate_trigrams(text):
    """Generuje trigramy (sekwencje 3 znaków) z danego tekstu."""
    text = normalize_text(text).replace(" ", "")
    if len(text) < 3:
        return {text}
    return {text[i:i+3] for i in range(len(text) - 2)}

def fuzzy_matching(item_name_list, ocr_candidate_name):
    """
    Sprawdza dopasowanie nazwy produktu z listy do nazwy z OCR przy użyciu trigramów
    i sprawdzania podciągów. Zwraca score podobieństwa.
    """
    if not item_name_list or not ocr_candidate_name:
        return 0.0
    normalized_item_name = normalize_text(item_name_list)
    normalized_ocr_name = normalize_text(ocr_candidate_name)

    # 1. Dokładne dopasowanie podciągów (priorytet)
    if normalized_item_name in normalized_ocr_name or normalized_ocr_name in normalized_item_name:
        return 1.0  # Idealne dopasowanie

    # 2. Dopasowanie trigramów (dla częściowych/skróconych nazw)
    item_trigrams = generate_trigrams(normalized_item_name)
    ocr_trigrams = generate_trigrams(normalized_ocr_name)

    if not item_trigrams or not ocr_trigrams:
        return 0.0

    # Obliczanie podobieństwa Jaccarda na trigramach
    intersection = len(item_trigrams.intersection(ocr_trigrams))
    union = len(item_trigrams.union(ocr_trigrams))

    jaccard_similarity = intersection / union if union > 0 else 0.0
    return jaccard_similarity


def match_ocr_to_shopping_list(shopping_list_items, parsed_ocr_items):
    """
    Łączy sparsowane wyniki OCR z istniejącymi elementami listy zakupów
    i dodaje nowe elementy znalezione tylko w OCR.

    Args:
        shopping_list_items (list): Lista słowników przedmiotów z listy zakupów,
                                    np. [{'name': 'Chleb', 'price': None, 'assigned_friends': []}, ...].
                                    Ceny są opcjonalne.
        parsed_ocr_items (list): Lista słowników przedmiotów uzyskanych po parsowaniu OCR,
                                 np. [{'name': 'Chleb pszenny', 'total_price': '3.49'}, ...].

    Returns:
        list: Zaktualizowana lista przedmiotów z uwzględnionymi cenami z OCR
              i nowymi przedmiotami znalezionymi tylko w OCR.
              Elementy zachowują strukturę podobną do shopping_list_items.
    """

    # Tworzymy kopię listy OCR, aby móc oznaczać dopasowane elementy
    # Upewniamy się, że mają klucz 'matched' ustawiony na False
    ocr_items_with_status = [{'name': item['name'], 'price': Decimal(item['total_price']), 'matched': False}
                             for item in parsed_ocr_items if 'name' in item and 'total_price' in item]

    final_shopping_list = []
    threshold = 0.65  # Próg podobieństwa trigramów (możesz dostosować)

    # 1. Dopasowanie elementów listy zakupów do elementów z OCR
    for s_item in shopping_list_items:
        s_item_name_normalized = normalize_text(s_item['name'])
        best_match_ocr_idx = -1
        highest_similarity = -1.0

        for i, ocr_item in enumerate(ocr_items_with_status):
            if ocr_item['matched']:  # Pomijamy już dopasowane elementy OCR
                continue

            similarity = fuzzy_matching(s_item_name_normalized, ocr_item['name'])

            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match_ocr_idx = i

        if best_match_ocr_idx != -1 and highest_similarity >= threshold:
            # Dopasowano element z listy zakupów do elementu OCR
            matched_ocr_item = ocr_items_with_status[best_match_ocr_idx]

            # Aktualizujemy cenę elementu z listy zakupów, jeśli w OCR znaleziono cenę
            if matched_ocr_item['price'] is not None:
                s_item['price'] = matched_ocr_item['price']

            final_shopping_list.append(s_item)
            matched_ocr_item['matched'] = True  # Oznacz jako dopasowane, aby nie używać ponownie
        else:
            # Nie znaleziono wystarczająco dobrego dopasowania w OCR dla elementu z listy zakupów
            final_shopping_list.append(s_item)  # Zachowaj go z oryginalną ceną (lub None)

    # 2. Dodanie niepasujących elementów z OCR do listy końcowej
    for ocr_item in ocr_items_with_status:
        if not ocr_item['matched']:
            # Dodaj tylko jeśli ma nazwę i cenę
            if ocr_item['name'] and ocr_item['price'] is not None:
                # Tworzymy nową pozycję, zachowując strukturę jak w shopping_list_items
                final_shopping_list.append({
                    'name': ocr_item['name'],
                    'price': ocr_item['price'],
                    'assigned_friends': []  # Domyślnie pusta lista znajomych dla nowych pozycji
                })
            elif ocr_item['name'] and len(ocr_item['name'].split()) > 1:  # Dodaj jeśli nazwa jest wielowyrazowa
                final_shopping_list.append({'name': ocr_item['name'], 'price': None, 'assigned_friends': []})
            elif ocr_item['name'] and len(ocr_item['name']) >= 4:  # Dodaj jeśli nazwa jest pojedynczym, dłuższym słowem
                final_shopping_list.append({'name': ocr_item['name'], 'price': None, 'assigned_friends': []})

    return final_shopping_list
