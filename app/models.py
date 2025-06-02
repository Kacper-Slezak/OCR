# app/models.py
from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json # do obsługi json


@login_manager.user_loader
def load_user(user_id):

    return User.query.get(int(user_id))


# Tabela asocjacyjna dla relacji Many-to-Many między User a ShoppingList (uczestnicy)

shopping_list_participants = db.Table(
    'shopping_list_participants',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('shopping_list_id', db.Integer, db.ForeignKey('shopping_list.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacje do innych modeli
    created_shopping_lists = db.relationship('ShoppingList', backref='creator', lazy='dynamic', foreign_keys='ShoppingList.created_by')
    assigned_products = db.relationship('Product', backref='assigned_person', lazy='dynamic', foreign_keys='Product.assigned_to')
    paid_products = db.relationship('Product', backref='payer', lazy='dynamic', foreign_keys='Product.paid_by')
    debtor_settlements = db.relationship('Settlement', backref='debtor', lazy='dynamic', foreign_keys='Settlement.debtor_id')
    creditor_settlements = db.relationship('Settlement', backref='creditor', lazy='dynamic', foreign_keys='Settlement.creditor_id')
    uploaded_receipts = db.relationship('Receipt', backref='uploader', lazy='dynamic')
    participated_shopping_lists = db.relationship('ShoppingList', secondary=shopping_list_participants, backref=db.backref('participants', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_completed = db.Column(db.Boolean, default=False)

    # Relacje
    products = db.relationship('Product', backref='shopping_list', lazy='dynamic', cascade='all, delete-orphan')
    settlements = db.relationship('Settlement', backref='shopping_list_ref', lazy='dynamic', cascade='all, delete-orphan')
    # Relacja many-to-many do uczestników jest zdefiniowana w User (poprzez secondary=shopping_list_participants)

    def __repr__(self):
        return f'<ShoppingList {self.name}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Kto ma kupić/jest przypisany
    paid_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)     # Kto faktycznie zapłacił
    is_purchased = db.Column(db.Boolean, default=False)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipt.id'), nullable=True)  # Powiazanie produktu z paragonem

    def __repr__(self):
        return f'<Product {self.name} - {self.price}>'

class Settlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)
    debtor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creditor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    is_settled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime, nullable=True) # Data uregulowania

    # Indeksy dla szybszych zapytań (opcjonalne, ale zalecane dla kluczy obcych)
    __table_args__ = (
        db.Index('idx_settlement_list_id', 'shopping_list_id'),
        db.Index('idx_settlement_debtor_id', 'debtor_id'),
        db.Index('idx_settlement_creditor_id', 'creditor_id'),
    )

    def __repr__(self):
        return f'<Settlement {self.debtor_id} owes {self.creditor_id} {self.amount} for list {self.shopping_list_id}>'

class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='uploaded') # Status przetwarzania: 'uploaded', 'processing', 'processed', 'error'
    raw_text = db.Column(db.Text, nullable=True) # Surowy tekst z OCR
    processed_data = db.Column(db.Text, nullable=True) # Sparsowane dane w formacie JSON jako string

    # Relacja: Paragon może mieć wiele produktów (jeśli Product ma receipt_id)
    products_from_receipt = db.relationship('Product', backref='source_receipt', lazy='dynamic', cascade='all, delete-orphan')

    def set_processed_data(self, data):
        self.processed_data = json.dumps(data)

    def get_processed_data(self):
        if self.processed_data:
            return json.loads(self.processed_data)
        return None

    def __repr__(self):
        return f'<Receipt {self.id} - {self.status}>'