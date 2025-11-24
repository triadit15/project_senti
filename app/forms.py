# app/forms.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, DecimalField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, NumberRange, Optional
)

# ---------------------------
# USER REGISTRATION FORM
# ---------------------------
class RegisterForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=120)]
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6)]
    )
    confirm = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")]
    )
    is_merchant = BooleanField("Register as Merchant")
    submit = SubmitField("Register")


# ---------------------------
# LOGIN FORM
# ---------------------------
class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email()]
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()]
    )
    remember = BooleanField("Remember me")
    submit = SubmitField("Login")


# ---------------------------
# MANUAL REDEEM FORM
# ---------------------------
class VoucherForm(FlaskForm):
    code = StringField("Voucher Code", validators=[DataRequired(), Length(max=50)])
    submit = SubmitField("Redeem")


# ---------------------------
# MERCHANT CREATE VOUCHER FORM
# ---------------------------
class CreateVoucherForm(FlaskForm):
    # Merchant can optionally provide a custom code (if empty, system will generate one)
    code = StringField("Voucher code (optional)", validators=[Optional(), Length(max=50)])
    # Amount / value field (match routes which use .amount)
    amount = DecimalField(
        "Voucher Amount (R)",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2
    )
    submit = SubmitField("Create Voucher")