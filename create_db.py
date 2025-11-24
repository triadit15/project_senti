# create_db.py
from app import create_app, db
from app.models import User, Wallet
import os

app = create_app()
app.app_context().push()

# Path to database
db_path = os.path.join(app.instance_path, "senti.db")

# Remove old DB
if os.path.exists(db_path):
    print(f"Removing old DB: {db_path}")
    os.remove(db_path)

# Recreate DB
db.create_all()
print("Database created.")

# ---- CREATE DEFAULT ADMIN ----
admin = User(
    email="admin@senti.com",
    role="admin"     # ✔ No is_admin used
)
admin.set_password("adminpass123")

db.session.add(admin)
db.session.commit()

# ---- CREATE ADMIN WALLET ----
admin_wallet = Wallet(
    balance=0.0,
    user_id=admin.id
)

db.session.add(admin_wallet)
db.session.commit()

print("Admin created with wallet.")
print("Setup completed successfully.")