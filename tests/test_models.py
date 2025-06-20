# tests/test_models.py
import pytest
from app.models import User, ShoppingList, Product, Receipt, Settlement, shopping_list_participants
from app import create_app, mail
from datetime import datetime
from decimal import Decimal

# Testy dla modelu User
def test_user_creation(session):
    user = User(username='testuser_new', email='new@example.com')
    user.set_password('secure_password')
    session.add(user)
    session.commit()

    retrieved_user = User.query.filter_by(username='testuser_new').first()
    assert retrieved_user is not None
    assert retrieved_user.username == 'testuser_new'
    assert retrieved_user.email == 'new@example.com'
    assert retrieved_user.check_password('secure_password')
    assert not retrieved_user.check_password('wrong_password')

def test_user_unique_username(session, test_user): # Używamy fixture test_user
    new_user = User(username='testuser', email='another@example.com') # To samo username
    new_user.set_password('password')
    session.add(new_user)
    with pytest.raises(Exception): # Spodziewamy się błędu unikalności
        session.commit()
    session.rollback() # Wycofaj transakcję po błędzie

def test_user_unique_email(session, test_user):
    new_user = User(username='another_user', email='test@example.com') # Ten sam email
    new_user.set_password('password')
    session.add(new_user)
    with pytest.raises(Exception):
        session.commit()
    session.rollback()

# Testy dla modelu ShoppingList
def test_shopping_list_creation(session, test_user):
    shopping_list = ShoppingList(name='Weekly Groceries', created_by=test_user.id)
    session.add(shopping_list)
    session.commit()

    retrieved_list = ShoppingList.query.filter_by(name='Weekly Groceries').first()
    assert retrieved_list is not None
    assert retrieved_list.name == 'Weekly Groceries'
    assert retrieved_list.creator == test_user # Sprawdzenie relacji wstecznej
    assert not retrieved_list.is_completed

def test_shopping_list_participants(session, test_user):
    user2 = User(username='user2', email='user2@example.com')
    user2.set_password('pass2')
    session.add(user2)
    session.commit()

    shopping_list = ShoppingList(name='Party List', created_by=test_user.id)
    session.add(shopping_list)
    session.commit()

    # Dodaj uczestników do listy
    shopping_list.participants.append(test_user)
    shopping_list.participants.append(user2)
    session.commit()

    retrieved_list = ShoppingList.query.get(shopping_list.id)
    assert test_user in retrieved_list.participants.all()
    assert user2 in retrieved_list.participants.all()
    assert len(retrieved_list.participants.all()) == 2

    retrieved_user = User.query.get(test_user.id)
    assert shopping_list in retrieved_user.participated_shopping_lists.all()

# Testy dla modelu Product
def test_product_creation(session, test_user):
    shopping_list = ShoppingList(name='Electronics', created_by=test_user.id)
    session.add(shopping_list)
    session.commit()

    product = Product(name='Headphones', price=Decimal('99.99'),
                      shopping_list_id=shopping_list.id,
                      assigned_to=test_user.id, paid_by=test_user.id)
    session.add(product)
    session.commit()

    retrieved_product = Product.query.filter_by(name='Headphones').first()
    assert retrieved_product is not None
    assert retrieved_product.price == Decimal('99.99')
    assert retrieved_product.shopping_list == shopping_list # Sprawdzenie relacji
    assert retrieved_product.assigned_person == test_user
    assert retrieved_product.payer == test_user
    assert not retrieved_product.is_purchased

def test_product_delete_cascade_from_shopping_list(session, test_user):
    shopping_list = ShoppingList(name='Delete Test', created_by=test_user.id)
    session.add(shopping_list)
    session.commit()

    product = Product(name='Item to Delete', price=Decimal('10.00'), shopping_list_id=shopping_list.id)
    session.add(product)
    session.commit()

    product_id = product.id
    session.delete(shopping_list)
    session.commit()

    assert Product.query.get(product_id) is None # Produkt powinien zostać usunięty kaskadowo

# Testy dla modelu Receipt
def test_receipt_creation(session, test_user):
    receipt = Receipt(user_id=test_user.id, file_path='/path/to/receipt.jpg', status='uploaded')
    session.add(receipt)
    session.commit()

    retrieved_receipt = Receipt.query.filter_by(file_path='/path/to/receipt.jpg').first()
    assert retrieved_receipt is not None
    assert retrieved_receipt.uploader == test_user # Relacja
    assert retrieved_receipt.status == 'uploaded'

def test_receipt_processed_data(session, test_user):
    receipt = Receipt(user_id=test_user.id, file_path='/path/to/receipt2.jpg')
    processed_data = {
        "items": [
            {"name": "Milk", "price": 5.50},
            {"name": "Bread", "price": 4.00}
        ],
        "total": 9.50
    }
    receipt.set_processed_data(processed_data)
    session.add(receipt)
    session.commit()

    retrieved_receipt = Receipt.query.get(receipt.id)
    assert retrieved_receipt.get_processed_data() == processed_data

# Testy dla modelu Settlement
def test_settlement_creation(session, test_user):
    user2 = User(username='user_creditor', email='creditor@example.com')
    user2.set_password('pass')
    session.add(user2)
    session.commit()

    shopping_list = ShoppingList(name='Settlement List', created_by=test_user.id)
    session.add(shopping_list)
    session.commit()

    settlement = Settlement(shopping_list_id=shopping_list.id,
                            debtor_id=test_user.id,
                            creditor_id=user2.id,
                            amount=Decimal('25.50'))
    session.add(settlement)
    session.commit()

    retrieved_settlement = Settlement.query.filter_by(amount=Decimal('25.50')).first()
    assert retrieved_settlement is not None
    assert retrieved_settlement.debtor == test_user
    assert retrieved_settlement.creditor == user2
    assert retrieved_settlement.shopping_list_ref == shopping_list
    assert not retrieved_settlement.is_settled

def test_settlement_mark_settled(session, test_user):
    user2 = User(username='user_creditor2', email='creditor2@example.com')
    user2.set_password('pass')
    session.add(user2)
    session.commit()

    shopping_list = ShoppingList(name='Settlement List 2', created_by=test_user.id)
    session.add(shopping_list)
    session.commit()

    settlement = Settlement(shopping_list_id=shopping_list.id,
                            debtor_id=test_user.id,
                            creditor_id=user2.id,
                            amount=Decimal('50.00'))
    session.add(settlement)
    session.commit()

    retrieved_settlement = Settlement.query.get(settlement.id)
    retrieved_settlement.is_settled = True
    retrieved_settlement.settled_at = datetime.utcnow()
    session.commit()

    final_settlement = Settlement.query.get(settlement.id)
    assert final_settlement.is_settled
    assert final_settlement.settled_at is not None

# Test dla relacji Product z Receipt
def test_product_receipt_relation(session, test_user):
    receipt = Receipt(user_id=test_user.id, file_path='/path/to/test_receipt.jpg')
    session.add(receipt)
    session.commit()

    shopping_list = ShoppingList(name='Test List for Receipt', created_by=test_user.id)
    session.add(shopping_list)
    session.commit()

    product = Product(name='Test Product', price=Decimal('12.34'),
                      shopping_list_id=shopping_list.id,
                      receipt_id=receipt.id) # Powiąż z paragonem
    session.add(product)
    session.commit()

    retrieved_product = Product.query.get(product.id)
    assert retrieved_product.source_receipt == receipt
    assert retrieved_product.receipt_id == receipt.id

    retrieved_receipt = Receipt.query.get(receipt.id)
    assert product in retrieved_receipt.products_from_receipt.all()

# Testy dla modelu Wiadomości

def client(monkeypatch):
    app = create_app()
    app.config.update({
        'TESTING': True,
        'MAIL_SUPPRESS_SEND': True  # не шлём реально
    })
    return app.test_client()

def test_welcome_notification(client):
    resp = client.post('/notify/welcome', json={
        'email': 'test@example.com',
        'user_name': 'Игорь'
    })
    assert resp.status_code == 200

