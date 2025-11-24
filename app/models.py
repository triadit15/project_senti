from . import db, login_manager
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------
# USER MODEL
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), default="user")  # user | merchant | admin

    # One-to-one relationship with Wallet
    wallet = db.relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        cascade="all, delete",
    )

    # Password helpers
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


# ---------------------------------------------------------
# WALLET MODEL
# ---------------------------------------------------------
class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Float, default=0.0)

    # FK to User
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)

    user = db.relationship("User", back_populates="wallet")

    # Transactions linked to this wallet
    transactions = db.relationship("Transaction", backref="wallet", lazy=True)

    # Withdrawal requests
    withdrawal_requests = db.relationship("WithdrawalRequest", backref="wallet", lazy=True)


# ---------------------------------------------------------
# VOUCHER MODEL
# ---------------------------------------------------------
class Voucher(db.Model):
    __tablename__ = "vouchers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    is_redeemed = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    merchant_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    redeemer_id = db.Column(db.Integer, db.ForeignKey("users.id"))


# ---------------------------------------------------------
# TRANSACTION HISTORY
# ---------------------------------------------------------
class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))     # deposit, redemption, withdrawal
    amount = db.Column(db.Float)
    description = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id"))


# ---------------------------------------------------------
# WITHDRAWAL REQUESTS
# ---------------------------------------------------------
class WithdrawalRequest(db.Model):
    __tablename__ = "withdrawal_requests"

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id"))
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected
    account_number = db.Column(db.String(50))
    bank_name = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)