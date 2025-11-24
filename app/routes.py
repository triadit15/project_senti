import io
import qrcode
import random
import string

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, send_file, abort
)
from flask_login import login_user, logout_user, login_required, current_user

from . import db
from .models import User, Wallet, Voucher, Transaction, WithdrawalRequest
from .forms import RegisterForm, LoginForm, VoucherForm, CreateVoucherForm

bp = Blueprint("main", __name__, url_prefix="/")


# ---------------------------
# UTILITIES
# ---------------------------
def ensure_wallet_for(user):
    """Ensure the logged-in user has a wallet."""
    if not user.wallet:
        wallet = Wallet(balance=0.0, user_id=user.id)
        db.session.add(wallet)
        db.session.commit()
        # reload relationship
        db.session.refresh(user)


def generate_voucher_code(length=10):
    """Generate a random alphanumeric voucher code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def log_transaction(wallet_id, trans_type, amount, description):
    """Save a wallet transaction to the ledger."""
    t = Transaction(
        wallet_id=wallet_id,
        type=trans_type,
        amount=amount,
        description=description
    )
    db.session.add(t)
    db.session.commit()


# ---------------------------
# HOME
# ---------------------------
@bp.route("/")
def home():
    return render_template("home.html")


# ---------------------------
# REGISTER
# ---------------------------
@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("main.login"))

        role = "merchant" if getattr(form, "is_merchant", None) and form.is_merchant.data else "consumer"

        user = User(email=email, role=role)
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # create wallet
        wallet = Wallet(balance=0.0, user_id=user.id)
        db.session.add(wallet)
        db.session.commit()

        flash("Account created. Please login.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", form=form)


# ---------------------------
# LOGIN
# ---------------------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=getattr(form, "remember", None) and form.remember.data)
            flash("Login successful.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))
        else:
            flash("Invalid credentials.", "danger")

    return render_template("login.html", form=form)


# ---------------------------
# LOGOUT
# ---------------------------
@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


# ---------------------------
# DASHBOARD
# ---------------------------
@bp.route("/dashboard")
@login_required
def dashboard():
    ensure_wallet_for(current_user)
    return render_template("dashboard.html", user=current_user)


# ---------------------------
# WALLET PAGE & MANUAL REDEEM
# ---------------------------
@bp.route("/wallet", methods=["GET", "POST"])
@login_required
def wallet():
    ensure_wallet_for(current_user)
    form = VoucherForm()

    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        v = Voucher.query.filter_by(code=code).first()

        if not v:
            flash("Voucher not found.", "danger")
        elif v.is_redeemed:
            flash("Voucher already redeemed.", "warning")
        else:
            # credit amount
            current_user.wallet.balance += v.amount
            v.is_redeemed = True
            v.redeemer_id = current_user.id
            db.session.commit()

            log_transaction(current_user.wallet.id, "credit", v.amount, f"Voucher redeemed: {v.code}")
            flash(f"R{v.amount:.2f} added to your wallet.", "success")

        return redirect(url_for("main.wallet"))

    return render_template("wallet.html", form=form, wallet=current_user.wallet)


# ---------------------------------------------
# WALLET DEPOSIT (SIMULATION)
# ---------------------------------------------
@bp.route("/wallet/deposit", methods=["GET", "POST"])
@login_required
def wallet_deposit():
    ensure_wallet_for(current_user)

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            flash("Invalid amount.", "danger")
            return redirect(url_for("main.wallet_deposit"))

        if amount <= 0:
            flash("Invalid amount.", "danger")
            return redirect(url_for("main.wallet_deposit"))

        current_user.wallet.balance += amount
        db.session.commit()

        log_transaction(current_user.wallet.id, "credit", amount, f"Deposit simulation of R{amount:.2f}")

        flash(f"Deposit successful! R{amount:.2f} added to your wallet.", "success")
        return redirect(url_for("main.wallet"))

    return render_template("wallet_deposit.html")


# ---------------------------------------------
# USER WITHDRAWAL REQUEST
# ---------------------------------------------
@bp.route("/wallet/withdraw", methods=["GET", "POST"])
@login_required
def wallet_withdraw():
    ensure_wallet_for(current_user)

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            flash("Invalid amount.", "danger")
            return redirect(url_for("main.wallet_withdraw"))

        if amount <= 0:
            flash("Invalid amount.", "danger")
            return redirect(url_for("main.wallet_withdraw"))

        if amount > current_user.wallet.balance:
            flash("Insufficient funds.", "danger")
            return redirect(url_for("main.wallet_withdraw"))

        wr = WithdrawalRequest(
            wallet_id=current_user.wallet.id,
            amount=amount,
            status="pending"
        )
        db.session.add(wr)
        db.session.commit()

        flash("Withdrawal request submitted. Admin will review it shortly.", "info")
        return redirect(url_for("main.wallet"))

    return render_template("wallet_withdraw.html")


# ---------------------------------------------
# USER PROFILE
# ---------------------------------------------
@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        new_email = request.form.get("new_email")
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")

        updated = False

        if new_email and new_email != current_user.email:
            current_user.email = new_email.strip().lower()
            updated = True
            flash("Email updated successfully.", "success")

        if current_password and new_password:
            if current_user.check_password(current_password):
                current_user.set_password(new_password)
                updated = True
                flash("Password updated successfully.", "success")
            else:
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("main.profile"))

        if updated:
            db.session.commit()
        else:
            flash("No changes were made.", "info")

        return redirect(url_for("main.profile"))

    return render_template("profile.html")


# ---------------------------
# QR AUTO REDEEM
# ---------------------------
@bp.route("/redeem/<code>")
@login_required
def redeem_voucher(code):
    v = Voucher.query.filter_by(code=code).first()

    if not v:
        flash("Voucher not found.", "danger")
        return redirect(url_for("main.wallet"))

    if v.is_redeemed:
        flash("Voucher already redeemed.", "warning")
        return redirect(url_for("main.wallet"))

    ensure_wallet_for(current_user)

    current_user.wallet.balance += v.amount
    v.is_redeemed = True
    v.redeemer_id = current_user.id
    db.session.commit()

    log_transaction(current_user.wallet.id, "credit", v.amount, f"Voucher redeemed via QR: {v.code}")

    flash(f"Voucher redeemed: R{v.amount:.2f} credited.", "success")
    return redirect(url_for("main.wallet"))


# ---------------------------
# QR IMAGE GENERATION
# ---------------------------
@bp.route("/voucher/<code>/qrcode")
def voucher_qr(code):
    v = Voucher.query.filter_by(code=code).first_or_404()
    redeem_url = url_for("main.redeem_voucher", code=v.code, _external=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=7,
        border=2,
    )
    qr.add_data(redeem_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


# ---------------------------
# MERCHANT: CREATE VOUCHER (AUTO CODE)
# ---------------------------
@bp.route("/merchant/create_voucher", methods=["GET", "POST"])
@login_required
def merchant_create_voucher():
    if current_user.role not in ["merchant", "admin"]:
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    form = CreateVoucherForm()

    if form.validate_on_submit():
        code = generate_voucher_code()
        while Voucher.query.filter_by(code=code).first():
            code = generate_voucher_code()

        v = Voucher(code=code, amount=float(form.amount.data), merchant_id=current_user.id)
        db.session.add(v)
        db.session.commit()

        flash(f"Voucher created: {code}", "success")
        return redirect(url_for("main.voucher_created", code=code))

    return render_template("create_voucher.html", form=form)


# ---------------------------
# MERCHANT: LIST ALL CREATED VOUCHERS
# ---------------------------
@bp.route("/merchant/vouchers")
@login_required
def merchant_voucher_list():
    if current_user.role not in ["merchant", "admin"]:
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    vouchers = Voucher.query.order_by(Voucher.id.desc()).all()
    return render_template("merchant_vouchers.html", vouchers=vouchers)


# ---------------------------
# VOUCHER CREATED (SHOW QR)
# ---------------------------
@bp.route("/voucher/created/<code>")
@login_required
def voucher_created(code):
    if current_user.role not in ["merchant", "admin"]:
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    v = Voucher.query.filter_by(code=code).first_or_404()
    qr_url = url_for("main.voucher_qr", code=v.code)
    redeem_url = url_for("main.redeem_voucher", code=v.code, _external=True)

    return render_template("voucher_created.html", voucher=v, qr_url=qr_url, redeem_url=redeem_url)


# ---------------------------
# TRANSACTION HISTORY
# ---------------------------
@bp.route("/wallet/history")
@login_required
def wallet_history():
    ensure_wallet_for(current_user)
    history = current_user.wallet.transactions
    return render_template("wallet_history.html", history=history)


# ---------------------------
# QR SCANNER PAGE
# ---------------------------
@bp.route("/scan")
@login_required
def qr_scanner():
    return render_template("qr_scanner.html")


# ---------------------------
# ADMIN DASHBOARD
# ---------------------------
@bp.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("main.dashboard"))

    total_users = User.query.count()
    total_merchants = User.query.filter_by(role="merchant").count()
    total_vouchers = Voucher.query.count()
    redeemed_vouchers = Voucher.query.filter_by(is_redeemed=True).count()
    unredeemed_vouchers = total_vouchers - redeemed_vouchers
    total_balance = db.session.query(db.func.sum(Wallet.balance)).scalar() or 0
    recent = Transaction.query.order_by(Transaction.timestamp.desc()).limit(10).all()

    return render_template("admin_dashboard.html",
                           total_users=total_users,
                           total_merchants=total_merchants,
                           total_vouchers=total_vouchers,
                           redeemed_vouchers=redeemed_vouchers,
                           unredeemed_vouchers=unredeemed_vouchers,
                           total_balance=total_balance,
                           recent=recent)


# ---------------------------------------------
# ADMIN: VIEW & APPROVE WITHDRAWALS
# ---------------------------------------------
@bp.route("/admin/withdrawals")
@login_required
def admin_withdrawals():
    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("main.dashboard"))

    pending = WithdrawalRequest.query.filter_by(status="pending").all()
    approved = WithdrawalRequest.query.filter_by(status="approved").all()

    return render_template("admin_withdrawals.html", pending=pending, approved=approved)


@bp.route("/admin/withdrawals/approve/<int:id>")
@login_required
def approve_withdrawal(id):
    if current_user.role != "admin":
        flash("Admin access required.", "danger")
        return redirect(url_for("main.dashboard"))

    wr = WithdrawalRequest.query.get_or_404(id)
    if wr.status == "approved":
        flash("Already approved.", "info")
        return redirect(url_for("main.admin_withdrawals"))

    wallet = Wallet.query.get(wr.wallet_id)
    if wallet.balance < wr.amount:
        flash("User wallet has insufficient funds.", "danger")
        return redirect(url_for("main.admin_withdrawals"))

    wallet.balance -= wr.amount
    wr.status = "approved"

    txn = Transaction(wallet_id=wallet.id, amount=wr.amount, type="debit", description=f"Withdrawal approved (R{wr.amount:.2f})")
    db.session.add(txn)
    db.session.commit()

    flash("Withdrawal approved successfully.", "success")
    return redirect(url_for("main.admin_withdrawals"))