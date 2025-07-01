from flask import Blueprint, redirect, url_for, render_template, request, flash
from flask_login import current_user, login_required
from decimal import Decimal  # Import Decimal
from app import db
from app.models import ShoppingList, Friend, Product, Settlement, User  # Dodano User do importów
from datetime import datetime
from sqlalchemy.exc import IntegrityError

# POPRAWKA: Upewnij się, że importujesz obie funkcje z settlement_service
from app.services.settlements_services import calculate_settlements, _check_and_update_list_settlement_status

bp = Blueprint('main', __name__)


@bp.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        # --- Obsługa formularza dodawania/usuwania znajomych ---
        if 'new-friend-name' in request.form and 'new-friend-email' in request.form:
            new_friend_name = request.form.get('new-friend-name').strip()
            new_friend_email = request.form.get('new-friend-email').strip()
            if not new_friend_name:
                flash('Nazwa znajomego nie może być pusta!', 'warning')
            elif not new_friend_email:
                flash('Adres e-mail znajomego nie może być pusty!', 'warning')
            else:
                existing_friend_by_name = Friend.query.filter_by(name=new_friend_name, user_id=current_user.id).first()
                existing_friend_by_email = Friend.query.filter_by(email=new_friend_email,
                                                                  user_id=current_user.id).first()

                if existing_friend_by_name:
                    flash(f'Znajomy o imieniu "{new_friend_name}" już istnieje w Twojej liście!', 'warning')
                elif existing_friend_by_email:
                    flash(f'Znajomy o adresie e-mail "{new_friend_email}" już istnieje w Twojej liście!', 'warning')
                else:
                    new_friend = Friend(name=new_friend_name, email=new_friend_email, user_id=current_user.id)
                    db.session.add(new_friend)
                    try:
                        db.session.commit()
                        flash(f'Znajomy "{new_friend_name}" ({new_friend_email}) został dodany!', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Błąd podczas dodawania znajomego: {e}', 'danger')
            return redirect(url_for('main.dashboard'))

        if 'remove_friend_id' in request.form:
            friend_id_to_remove = request.form.get('remove_friend_id')
            friend_to_remove = Friend.query.filter_by(id=friend_id_to_remove, user_id=current_user.id).first()
            if friend_to_remove:
                try:
                    # Usuwanie powiązań z produktami
                    # Zmiana: iteruj po kopii, aby uniknąć błędu RuntimeError: dictionary changed size during iteration
                    for product in list(friend_to_remove.assigned_products):
                        if friend_to_remove in product.assigned_friends_for_product:
                            product.assigned_friends_for_product.remove(friend_to_remove)

                    # Usuwanie powiązań z rozliczeniami, gdzie znajomy jest dłużnikiem
                    # Zmiana: .all() jest poprawne dla dynamicznych relacji
                    if hasattr(friend_to_remove, 'debtor_settlements_friend'):
                        for settlement in friend_to_remove.debtor_settlements_friend.all():
                            db.session.delete(settlement)
                    # Usuwanie powiązań z rozliczeniami, gdzie znajomy jest wierzycielem
                    if hasattr(friend_to_remove, 'creditor_settlements_friend'):
                        for settlement in friend_to_remove.creditor_settlements_friend.all():
                            db.session.delete(settlement)

                    db.session.delete(friend_to_remove)
                    db.session.commit()
                    flash(f'Znajomy "{friend_to_remove.name}" został usunięty.', 'info')
                except IntegrityError:
                    db.session.rollback()
                    flash(
                        f'Nie można usunąć znajomego "{friend_to_remove.name}", ponieważ jest powiązany z istniejącymi danymi.',
                        'danger')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Błąd podczas usuwania znajomego: {e}', 'danger')
            else:
                flash('Nie znaleziono znajomego do usunięcia lub nie masz uprawnień.', 'danger')
            # Ważne: Zawsze przekieruj po operacji POST
            return redirect(url_for('main.dashboard'))

        # --- NOWA LOGIKA: Obsługa formularza zapisu listy zakupów ---
        # Ta sekcja jest dla edycji/tworzenia listy, która powinna być w 'receipt_bp'
        # Jeśli ten kod jest w 'main.py' i chcesz go tu zachować, upewnij się, że jest poprawny.
        # Wcześniejsze dyskusje sugerowały przeniesienie tej logiki do 'receipt_bp'.
        # Na potrzeby tego zadania, nie zmieniam tej logiki, tylko dodaję nową trasę.
        if 'list_name' in request.form and any(key.startswith('products[') for key in request.form):
            try:
                list_id = request.form.get('list_id')
                list_name = request.form.get('list_name').strip()

                status_str = request.form.get('is_fully_settled', 'False')
                is_fully_settled = (status_str == 'True')

                if not list_name:
                    list_name = f"Lista zakupów {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                shopping_list = None
                if list_id:
                    shopping_list = ShoppingList.query.get(list_id)
                    if shopping_list and shopping_list.created_by == current_user.id:
                        shopping_list.name = list_name
                        shopping_list.is_fully_settled = is_fully_settled
                        # Usuń wszystkie stare produkty z tej listy przed dodaniem nowych
                        for product in shopping_list.products.all():
                            db.session.delete(product)
                        db.session.commit()
                        flash('Edytowano listę zakupów.', 'info')
                    else:
                        flash('Nie znaleziono listy do edycji lub nie masz uprawnień.', 'danger')
                        return redirect(url_for('main.dashboard'))
                else:
                    shopping_list = ShoppingList(name=list_name, created_by=current_user.id,
                                                 is_fully_settled=is_fully_settled)
                    db.session.add(shopping_list)
                    db.session.commit()
                    flash('Lista zakupów została pomyślnie zapisana!', 'success')

                products_data = []
                product_indices = set()
                for key in request.form.keys():
                    if key.startswith('products[') and ']' in key:
                        try:
                            index_str = key.split('[')[1].split(']')[0]
                            product_indices.add(int(index_str))
                        except (ValueError, IndexError):
                            continue

                for index in sorted(list(product_indices)):
                    product_name = request.form.get(f'products[{index}][name]', '').strip()
                    if not product_name:
                        continue

                    assigned_friend_ids = request.form.getlist(f'products[{index}][friends][]')

                    # Pobierz cenę, jeśli istnieje
                    product_price_str = request.form.get(f'products[{index}][price]', '0.00').strip()
                    try:
                        product_price = Decimal(product_price_str.replace(',', '.'))
                    except Exception:
                        product_price = Decimal('0.00')  # Domyślna wartość w przypadku błędu

                    products_data.append({
                        'name': product_name,
                        'price': product_price,
                        'friends': assigned_friend_ids
                    })

                if shopping_list:
                    for product_data in products_data:
                        new_product = Product(
                            name=product_data['name'],
                            price=product_data['price'],
                            shopping_list_id=shopping_list.id,
                            paid_by=current_user.id  # POPRAWKA: Ustawienie kto zapłacił za produkt
                        )
                        db.session.add(new_product)

                        for friend_id in product_data['friends']:
                            friend = Friend.query.get(friend_id)
                            if friend and friend.user_id == current_user.id:
                                new_product.assigned_friends_for_product.append(friend)
                    db.session.commit()

                return redirect(url_for('main.dashboard'))

            except IntegrityError as e:
                db.session.rollback()
                flash(f'Wystąpił błąd podczas zapisywania listy zakupów (Integralność danych): {e}', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'Wystąpił nieoczekiwany błąd podczas zapisywania listy: {e}', 'danger')

            return redirect(url_for('main.dashboard'))

    # --- Logika dla żądań GET (wyświetlanie dashboardu) ---
    # Pobieramy listy zakupów, w których użytkownik jest twórcą LUB uczestnikiem.
    my_shopping_lists_as_participant = ShoppingList.query \
        .join(ShoppingList.participants) \
        .filter(User.id == current_user.id) \
        .all()

    my_created_shopping_lists = ShoppingList.query.filter_by(created_by=current_user.id).all()

    # Łączymy listy i usuwamy duplikaty
    all_user_lists_dict = {lst.id: lst for lst in my_shopping_lists_as_participant + my_created_shopping_lists}

    # Sortujemy listy
    sorted_user_lists = sorted(all_user_lists_dict.values(), key=lambda x: x.created_at, reverse=True)

    friends = current_user.friends_owned.all()

    return render_template('main/dashboard.html', lists=sorted_user_lists, friends=friends)


@bp.route('/calculate_all_unsettled_lists', methods=['POST'])
@login_required
def calculate_all_unsettled_lists():
    """
    Trasa do przeliczania rozliczeń dla wszystkich nierozliczonych list zakupów bieżącego użytkownika.
    """
    user_id = current_user.id
    processed_count = 0

    # Znajdź wszystkie listy, gdzie użytkownik jest twórcą LUB uczestnikiem
    # i które nie są jeszcze w pełni rozliczone
    unsettled_lists = ShoppingList.query.filter(
        (ShoppingList.created_by == user_id) |
        ShoppingList.participants.any(User.id == user_id),
        ShoppingList.is_fully_settled == False  # Tylko te, które nie są w pełni rozliczone
    ).all()

    if not unsettled_lists:
        flash('Brak list oczekujących na rozliczenie.', 'info')
        # POPRAWKA: Przekierowanie na dashboard rozliczeń
        return redirect(url_for('settlements.settlements_dashboard'))

    for shopping_list in unsettled_lists:
        try:
            # Wyczyść istniejące rozliczenia dla tej listy przed ponownym przeliczeniem
            # WAŻNE: To usunie WSZYSTKIE rozliczenia dla listy, niezależnie od statusu.
            # Jeśli chcesz zachować historię, potrzebna jest bardziej złożona strategia.
            Settlement.query.filter_by(shopping_list_id=shopping_list.id).delete()
            db.session.commit()  # Zatwierdź usunięcie przed generowaniem nowych

            calculate_settlements(shopping_list.id)  # Wywołaj algorytm dla każdej listy
            processed_count += 1
        except Exception as e:
            db.session.rollback()
            flash(f'Błąd podczas obliczania rozliczeń dla listy "{shopping_list.name}": {e}', 'danger')
            # Nie przerywamy pętli, aby spróbować obliczyć pozostałe listy

    if processed_count > 0:
        flash(f'Pomyślnie obliczono rozliczenia dla {processed_count} list.', 'success')
    else:
        flash('Brak list do przetworzenia lub wystąpiły błędy.', 'info')

    # POPRAWKA: Przekierowanie na dashboard rozliczeń
    return redirect(url_for('settlements.settlements_dashboard'))

