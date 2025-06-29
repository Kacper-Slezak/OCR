import json
from flask import Blueprint, redirect, url_for, render_template, request, flash
from flask_login import current_user, login_required

from app import db
from app.models import ShoppingList, Friend, Product
from datetime import datetime
from sqlalchemy.exc import IntegrityError

bp = Blueprint('main', __name__)


@bp.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        # --- Obsługa formularza dodawania/usuwania znajomych ---
        if 'new-friend-name' in request.form:
            new_friend_name = request.form.get('new-friend-name').strip()
            if new_friend_name:
                existing_friend = Friend.query.filter_by(name=new_friend_name, user_id=current_user.id).first()
                if existing_friend:
                    flash(f'Znajomy o imieniu "{new_friend_name}" już istnieje!', 'warning')
                else:
                    new_friend = Friend(name=new_friend_name, email=f"{new_friend_name.lower()}@example.com",
                                        user_id=current_user.id)
                    db.session.add(new_friend)
                    try:
                        db.session.commit()
                        flash(f'Znajomy "{new_friend_name}" został dodany!', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Błąd podczas dodawania znajomego: {e}', 'danger')
            else:
                flash('Nazwa znajomego nie może być pusta!', 'warning')
            return redirect(url_for('main.dashboard'))

        if 'remove_friend_id' in request.form:
            friend_id_to_remove = request.form.get('remove_friend_id')
            friend_to_remove = Friend.query.filter_by(id=friend_id_to_remove, user_id=current_user.id).first()
            if friend_to_remove:
                try:
                    for product in friend_to_remove.assigned_products:
                        if friend_to_remove in product.assigned_friends_for_product:
                            product.assigned_friends_for_product.remove(friend_to_remove)
                    if hasattr(friend_to_remove, 'debtor_settlements_friend'):
                        for settlement in friend_to_remove.debtor_settlements_friend.all():
                            db.session.delete(settlement)
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
            return redirect(url_for('main.dashboard'))

        # --- NOWA LOGIKA: Obsługa formularza zapisu listy zakupów ---
        if 'list_name' in request.form and any(key.startswith('products[') for key in request.form):
            try:
                list_name = request.form.get('list_name').strip()
                if not list_name:
                    list_name = f"Lista zakupów {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                list_id = request.form.get('list_id')
                shopping_list = None
                if list_id:
                    shopping_list = ShoppingList.query.get(list_id)
                    if shopping_list and shopping_list.created_by == current_user.id:
                        shopping_list.name = list_name
                        # Usuń wszystkie stare produkty z tej listy przed dodaniem nowych
                        for product in shopping_list.products.all():
                            db.session.delete(product)
                        db.session.commit()  # Zatwierdź usunięcie produktów przed dodaniem nowych
                        flash('Edytowano listę zakupów.', 'info')
                    else:
                        flash('Nie znaleziono listy do edycji lub nie masz uprawnień.', 'danger')
                        return redirect(url_for('main.dashboard'))
                else:  # Nowa lista
                    shopping_list = ShoppingList(name=list_name, created_by=current_user.id)
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