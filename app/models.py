# app/models.py
from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Tabela asocjacyjna dla relacji Many-to-Many między User a ShoppingList (uczestnicy)
shopping_list_participants = db.Table(
    'shopping_list_participants',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('shopping_list_id', db.Integer, db.ForeignKey('shopping_list.id'), primary_key=True)
)

# Tabela asocjacyjna dla relacji Many-to-Many między Product a Friend (osoby przypisane do produktu)
product_friend_assignment = db.Table(
    'product_friend_assignment',
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('friend.id'), primary_key=True)
)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relacje do innych modeli
    created_shopping_lists = db.relationship('ShoppingList', backref='creator', lazy='dynamic',
                                             foreign_keys='ShoppingList.created_by')

    paid_products = db.relationship('Product', backref='payer', lazy='dynamic', foreign_keys='Product.paid_by')

    # Rozliczenia, gdzie użytkownik jest dłużnikiem
    debtor_settlements_user = db.relationship('Settlement', foreign_keys='Settlement.debtor_user_id',
                                              backref='debtor_user', lazy='dynamic')

    # Rozliczenia, gdzie użytkownik jest wierzycielem
    creditor_settlements_user = db.relationship('Settlement', foreign_keys='Settlement.creditor_user_id',
                                                backref='creditor_user', lazy='dynamic')

    uploaded_receipts = db.relationship('Receipt', backref='uploader', lazy='dynamic')

    # Relacja Many-to-Many do list zakupów, w których użytkownik jest uczestnikiem
    participated_shopping_lists = db.relationship(
        'ShoppingList',
        secondary=shopping_list_participants,
        backref=db.backref('participants', lazy='dynamic')
    )

    # Relacja do znajomych stworzonych przez użytkownika
    friends_owned = db.relationship('Friend', backref='owner', lazy='dynamic', foreign_keys='Friend.user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)g
    created_at = db.Column(db.DateTime, default=datetime.now)
    is_completed = db.Column(db.Boolean, default=False)
    # NOWA KOLUMNA: Status rozliczenia całej listy
    is_fully_settled = db.Column(db.Boolean, default=False, nullable=False)

    # Relacje
    products = db.relationship('Product', backref='shopping_list', lazy='dynamic', cascade='all, delete-orphan')
    settlements = db.relationship('Settlement', backref='shopping_list_ref', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ShoppingList {self.name}>'


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)

    # Relacja Many-to-Many: znajomi przypisani do danego produktu
    assigned_friends_for_product = db.relationship(
        'Friend',
        secondary=product_friend_assignment,
        back_populates='assigned_products'
    )

    paid_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Kto faktycznie zapłacił
    is_purchased = db.Column(db.Boolean, default=False)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipt.id'), nullable=True)  # Powiazanie produktu z paragonem

    def __repr__(self):
        return f'<Product {self.name} - {self.price}>'


class Settlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)

    # Nowe kolumny dla dłużnika (User lub Friend)
    debtor_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    debtor_friend_id = db.Column(db.Integer, db.ForeignKey('friend.id'), nullable=True)

    # Nowe kolumny dla wierzyciela (User lub Friend)
    creditor_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    creditor_friend_id = db.Column(db.Integer, db.ForeignKey('friend.id'), nullable=True)

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    is_settled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    settled_at = db.Column(db.DateTime, nullable=True)

    # Sprawdzenie, czy tylko jeden z pól dłużnika/wierzyciela jest wypełniony
    __table_args__ = (
        db.CheckConstraint(
            '(debtor_user_id IS NOT NULL AND debtor_friend_id IS NULL) OR '
            '(debtor_user_id IS NULL AND debtor_friend_id IS NOT NULL)',
            name='chk_debtor_type'
        ),
        db.CheckConstraint(
            '(creditor_user_id IS NOT NULL AND creditor_friend_id IS NULL) OR '
            '(creditor_user_id IS NULL AND creditor_friend_id IS NOT NULL)',
            name='chk_creditor_type'
        ),
        db.Index('idx_settlement_list_id', 'shopping_list_id'),
        db.Index('idx_settlement_debtor_user_id', 'debtor_user_id'),
        db.Index('idx_settlement_debtor_friend_id', 'debtor_friend_id'),
        db.Index('idx_settlement_creditor_user_id', 'creditor_user_id'),
        db.Index('idx_settlement_creditor_friend_id', 'creditor_friend_id'),
    )

    def __repr__(self):
        debtor_name = "N/A"
        if self.debtor_user:
            debtor_name = self.debtor_user.username
        elif self.debtor_friend:
            debtor_name = self.debtor_friend.name

        creditor_name = "N/A"
        if self.creditor_user:
            creditor_name = self.creditor_user.username
        elif self.creditor_friend:
            creditor_name = self.creditor_friend.name

        return f'<Settlement {debtor_name} owes {creditor_name} {self.amount} for list {self.shopping_list_id}>'


class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(50),
                       default='uploaded')  # Status przetwarzania: 'uploaded', 'processing', 'processed', 'error'
    raw_text = db.Column(db.Text, nullable=True)  # Surowy tekst z OCR
    processed_data = db.Column(db.Text, nullable=True)  # Sparsowane dane w formacie JSON jako string
    # NOWA Kolumna:
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=True)

    # Relacja: Paragon może mieć wiele produktów (jeśli Product ma receipt_id)
    products_from_receipt = db.relationship('Product', backref='source_receipt', lazy='dynamic',
                                            cascade='all, delete-orphan')

    def set_processed_data(self, data):
        self.processed_data = json.dumps(data)

    def get_processed_data(self):
        if self.processed_data:
            return json.loads(self.processed_data)
        return None

    def __repr__(self):
        return f'<Receipt {self.id} - {self.status}>'


class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relacja z produktami – wiele do wielu (produkty przypisane do tego znajomego)
    assigned_products = db.relationship(
        'Product',
        secondary=product_friend_assignment,
        back_populates='assigned_friends_for_product'
    )

    # Rozliczenia, gdzie znajomy jest dłużnikiem
    debtor_settlements_friend = db.relationship('Settlement', foreign_keys='Settlement.debtor_friend_id',
                                                backref='debtor_friend', lazy='dynamic')

    # Rozliczenia, gdzie znajomy jest wierzycielem
    creditor_settlements_friend = db.relationship('Settlement', foreign_keys='Settlement.creditor_friend_id',
                                                  backref='creditor_friend', lazy='dynamic')

    def __repr__(self):
        return f'<Friend {self.name} - {self.email}>'
