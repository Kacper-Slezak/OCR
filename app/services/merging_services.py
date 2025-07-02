import re
from decimal import Decimal, InvalidOperation  # Dodano InvalidOperation


def normalize_text(text):
    """Normalizuje tekst do porównań (małe litery, usuwanie znaków specjalnych)."""
    if not isinstance(text, str):
        return ""
    # Usuwamy kropki, przecinki, procenty, nawiasy itp. ale zachowujemy spacje, aby nie łączyć słów
    text = re.sub(r'[^a-z0-9\s]', '', text.lower())
    return ' '.join(text.split())


def generate_trigrams(text):
    """Generuje trigramy (sekwencje 3 znaków) z danego tekstu."""
    text = normalize_text(text).replace(" ", "")  # Usuwamy spacje dla trigramów
    if len(text) < 3:
        return {text}  # Zwróć cały tekst jako "trigram", jeśli jest za krótki
    return {text[i:i + 3] for i in range(len(text) - 2)}


def fuzzy_matching(item_name_list, ocr_candidate_name):
    """
    Sprawdza dopasowanie nazwy produktu z listy do nazwy z OCR przy użyciu trigramów
    i sprawdzania podciągów. Zwraca wynik podobieństwa.
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
                                    np. [{'name': 'Chleb', 'price': Decimal('0.00'), 'assigned_friends': [], 'paid_by': 1, 'db_id': 1}, ...].
                                    Ceny są obiektami Decimal.
        parsed_ocr_items (list): Lista słowników przedmiotów uzyskanych po parsowaniu OCR,
                                 np. [{'name': 'Chleb pszenny', 'total_price': '3.49'}, ...].
                                 'total_price' jest stringiem.

    Returns:
        list: Zaktualizowana lista przedmiotów z uwzględnionymi cenami z OCR
              i nowymi przedmiotami znalezionymi tylko w OCR.
              Elementy zachowują strukturę podobną do shopping_list_items.
    """

    # Tworzymy kopię listy OCR, aby móc oznaczać dopasowane elementy
    ocr_items_with_status = []
    for item in parsed_ocr_items:
        if 'name' in item and 'total_price' in item:
            try:
                # Konwertuj total_price na Decimal tutaj
                ocr_items_with_status.append({
                    'name': item['name'],
                    'price': Decimal(item['total_price']),
                    'matched': False
                })
            except InvalidOperation:
                print(
                    f"WARNING: Nie można przekonwertować ceny OCR '{item['total_price']}' dla '{item['name']}' na Decimal. Ustawiam cenę na 0.00.")
                ocr_items_with_status.append({
                    'name': item['name'],
                    'price': Decimal('0.00'),  # Ustaw cenę na 0.00, jeśli konwersja się nie powiedzie
                    'matched': False
                })

    final_shopping_list = []
    threshold = 0.45  # Próg podobieństwa trigramów (możesz dostosować)

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
            # i jest ona różna od 0.00 (lub jeśli oryginalna cena była 0.00, a OCR znalazł niezerową)
            if matched_ocr_item['price'] is not None and \
                    (matched_ocr_item['price'] != Decimal('0.00') or s_item['price'] == Decimal('0.00')):
                s_item['price'] = matched_ocr_item['price']

            final_shopping_list.append(s_item)
            matched_ocr_item['matched'] = True  # Oznacz jako dopasowane, aby nie używać ponownie
        else:
            # Nie znaleziono wystarczająco dobrego dopasowania w OCR dla elementu z listy zakupów
            final_shopping_list.append(s_item)  # Zachowaj go z oryginalną ceną (lub 0.00)

    # 2. Dodanie niepasujących elementów z OCR do listy końcowej
    for ocr_item in ocr_items_with_status:
        if not ocr_item['matched']:
            # Dodaj tylko jeśli ma nazwę i sensowną cenę, lub wystarczająco długą nazwę
            if ocr_item['name'] and (ocr_item['price'] is not None and ocr_item['price'] != Decimal('0.00')) or \
                    (ocr_item['name'] and len(ocr_item['name'].split()) > 1) or \
                    (ocr_item['name'] and len(ocr_item['name']) >= 4):  # Heurystyka dla sensownej nazwy
                # Tworzymy nową pozycję, zachowując strukturę jak w shopping_list_items
                final_shopping_list.append({
                    'name': ocr_item['name'],
                    'price': ocr_item['price'],
                    'assigned_friends': [],  # Domyślnie pusta lista znajomych dla nowych pozycji
                    'paid_by': None,  # Zostanie ustawione na current_user.id w trasie
                    'db_id': None  # Nowy element, brak ID z bazy danych
                })
            else:
                print(f"DEBUG: Pomijam element OCR '{ocr_item.get('name', 'N/A')}' z powodu braku sensownych danych.")

    return final_shopping_list
