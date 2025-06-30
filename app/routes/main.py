import json
from flask import Blueprint, redirect, url_for, render_template, request, flash
from flask_login import current_user, login_required

from app import db
from app.models import ShoppingList, Friend, Product, Settlement
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.services.settlements_services import calculate_settlements

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
                    for product in friend_to_remove.assigned_products:
                        if friend_to_remove in product.assigned_friends_for_product:
                            product.assigned_friends_for_product.remove(friend_to_remove)
                    # Usuwanie powiązań z rozliczeniami, gdzie znajomy jest dłużnikiem
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
        if 'list_name' in request.form and any(key.startswith('products[') for key in request.form):
            try:
                list_id = request.form.get('list_id')
                list_name = request.form.get('list_name').strip()

                status_str = request.form.get('is_fully_settled', 'False')
                is_fully_settled = (status_str == 'True')

                if not list_name:
                    list_name = f"Lista zakupów {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                list_id = request.form.get('list_id')
                shopping_list = None
                if list_id:
                    shopping_list = ShoppingList.query.get(list_id)
                    if shopping_list and shopping_list.created_by == current_user.id:
                        shopping_list.name = list_name
                        shopping_list.is_fully_settled = is_fully_settled  # *** ZAPIS STATUSU ***
                        # Usuń wszystkie stare produkty z tej listy przed dodaniem nowych
                        for product in shopping_list.products.all():
                            db.session.delete(product)
                        db.session.commit()  # Zatwierdź usunięcie produktów przed dodaniem nowych
                        flash('Edytowano listę zakupów.', 'info')
                    else:
                        flash('Nie znaleziono listy do edycji lub nie masz uprawnień.', 'danger')
                        return redirect(url_for('main.dashboard'))
                else:  # Nowa lista
                    shopping_list = ShoppingList(name=list_name, created_by=current_user.id, is_fully_settled=is_fully_settled)
                    db.session.add(shopping_list)
                    db.session.commit()  # Zapisz listę, aby otrzymać jej ID
                    flash('Lista zakupów została pomyślnie zapisana!', 'success')

                # NOWA LOGIKA PARSOWANIA DANYCH PRODUKTÓW Z FORMULARZA
                products_data = []
                # Iterujemy po indeksach produktów w formularzu
                # Formularz wysyła pola typu products[0][name], products[0][friends][], products[1][name], etc.
                # Aby poprawnie pobrać wszystkie checkbox'y, musimy użyć request.form.getlist()

                # Zbierz wszystkie unikalne indeksy produktów
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
                        continue  # Pomiń produkty bez nazwy

                    # Tutaj jest kluczowa zmiana: użyj getlist() do pobrania wszystkich zaznaczonych przyjaciół
                    assigned_friend_ids = request.form.getlist(f'products[{index}][friends][]')

                    products_data.append({
                        'name': product_name,
                        'price': 0.00,  # Domyślna cena, jeśli nie ma pola
                        'friends': assigned_friend_ids
                    })

                # Dodaj produkty do listy
                if shopping_list:
                    for product_data in products_data:
                        new_product = Product(
                            name=product_data['name'],
                            price=product_data['price'],
                            shopping_list_id=shopping_list.id
                        )
                        db.session.add(new_product)

                        for friend_id in product_data['friends']:
                            friend = Friend.query.get(friend_id)
                            if friend and friend.user_id == current_user.id:  # Sprawdź, czy znajomy należy do bieżącego użytkownika
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
    user_shopping_lists = ShoppingList.query.filter_by(created_by=current_user.id).order_by(
        ShoppingList.created_at.desc()).all()
    friends = current_user.friends_owned.all()

    return render_template('main/dashboard.html', lists=user_shopping_lists, friends=friends)

@bp.route('/calculate_all_unsettled_lists', methods=['POST'])
@login_required
def calculate_all_unsettled_lists():
    """
    Trasa do przeliczania rozliczeń dla wszystkich nierozliczonych list zakupów bieżącego użytkownika.
    """
    unsettled_lists = ShoppingList.query.filter_by(
        created_by=current_user.id,
        is_fully_settled=False
    ).all()

    total_settlements_generated = 0
    errors_occurred = False

    if not unsettled_lists:
        flash('Brak nierozliczonych list do przeliczenia.', 'info')
        return redirect(url_for('main.dashboard'))

    for s_list in unsettled_lists:
        try:
            # Wyczyść istniejące rozliczenia dla tej listy przed ponownym przeliczeniem
            Settlement.query.filter_by(shopping_list_id=s_list.id).delete()
            db.session.commit() # Zatwierdź usunięcie

            generated = calculate_settlements(s_list.id)
            total_settlements_generated += len(generated)
            print(f"Rozliczono listę '{s_list.name}' (ID: {s_list.id}). Wygenerowano {len(generated)} rozliczeń.")
        except Exception as e:
            db.session.rollback()
            flash(f'Wystąpił błąd podczas przeliczania rozliczeń dla listy "{s_list.name}": {e}', 'error')
            print(f"Błąd podczas przeliczania rozliczeń dla listy '{s_list.name}' (ID: {s_list.id}): {e}")
            errors_occurred = True

    if total_settlements_generated > 0:
        if errors_occurred:
            flash(f'Pomyślnie przeliczono rozliczenia dla niektórych list. Wystąpiły błędy dla innych.', 'warning')
        else:
            flash(f'Pomyślnie przeliczono rozliczenia dla wszystkich nierozliczonych list. Wygenerowano łącznie {total_settlements_generated} rozliczeń.', 'success')
    elif not errors_occurred: # Jeśli nie wygenerowano rozliczeń, ale też nie było błędów (np. brak produktów)
        flash('Rozliczenia zostały zresetowane dla wszystkich nierozliczonych list, ale nie wygenerowano nowych (prawdopodobnie brak produktów z cenami/przypisanymi osobami).', 'info')

    return redirect(url_for('main.dashboard'))