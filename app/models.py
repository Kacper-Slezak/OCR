from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    created_lists = db.relationship('ShoppingList', backref='creator', lazy=True)
    paid_products = db.relationship('Product', foreign_keys='Product.paid_by', backref='payer', lazy=True)
    assigned_products = db.relationship('Product', foreign_keys='Product.assigned_to', backref='assignee', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Association table for shopping list participants
shopping_list_participants = db.Table('shopping_list_participants',
                                      db.Column('shopping_list_id', db.Integer, db.ForeignKey('shopping_list.id'),
                                                primary_key=True),
                                      db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
                                      )

from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    created_lists = db.relationship('ShoppingList', backref='creator', lazy=True)
    paid_products = db.relationship('Product', foreign_keys='Product.paid_by', backref='payer', lazy=True)
    assigned_products = db.relationship('Product', foreign_keys='Product.assigned_to', backref='assignee', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Association table for shopping list participants
shopping_list_participants = db.Table('shopping_list_participants',
                                      db.Column('shopping_list_id', db.Integer, db.ForeignKey('shopping_list.id'),
                                                primary_key=True),
                                      db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
                                      )


class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_completed = db.Column(db.Boolean, default=False)

    # Relationships
    products = db.relationship('Product', backref='shopping_list', lazy=True, cascade='all, delete-orphan')
    participants = db.relationship('User', secondary=shopping_list_participants,
                                   backref=db.backref('participating_lists', lazy=True))
    receipts = db.relationship('Receipt', backref='shopping_list', lazy=True, cascade='all, delete-orphan')
    settlements = db.relationship('Settlement', backref='shopping_list', lazy=True, cascade='all, delete-orphan')

    def get_total_cost(self):
        return sum(product.price for product in self.products if product.is_purchased and product.price)

    def get_user_balance(self, user_id):
        """Returns balance for user (positive = owed money, negative = owes money)"""
        paid_amount = sum(p.price for p in self.products if p.paid_by == user_id and p.is_purchased and p.price)
        assigned_amount = sum(p.price for p in self.products if p.assigned_to == user_id and p.is_purchased and p.price)
        return paid_amount - assigned_amount

    def __repr__(self):
        return f'<ShoppingList {self.name}>'


class Settlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)
    debtor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creditor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    is_settled = db.Column(db.Boolean, default=False)
    settled_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    debtor = db.relationship('User', foreign_keys=[debtor_id], backref='debts')
    creditor = db.relationship('User', foreign_keys=[creditor_id], backref='credits')

    def mark_as_settled(self):
        self.is_settled = True
        self.settled_at = datetime.utcnow()

    def __repr__(self):
        return f'<Settlement {self.debtor.username} -> {self.creditor.username}: {self.amount}>'


class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    shopping_list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    ocr_text = db.Column(db.Text)
    is_processed = db.Column(db.Boolean, default=False)

    # Relationships
    products = db.relationship('Product', backref='receipt', lazy=True)
    uploader = db.relationship('User', backref='uploaded_receipts')

    def __repr__(self):
        return f'<Receipt {self.original_filename}>'