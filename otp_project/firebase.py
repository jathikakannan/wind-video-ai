import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Path to otp_project folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_PATH = os.path.join(BASE_DIR, "firebase_keys.json")

db = None  # default

# Initialize Firebase safely
if os.path.exists(FIREBASE_PATH):
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_PATH)
        firebase_admin.initialize_app(cred)

    db = firestore.client()
else:
    print(f"⚠️ Firebase JSON not found at {FIREBASE_PATH}")

# Save login
def save_login_to_cloud(email):
    if db:
        db.collection("logins").add({
            "email": email,
            "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    else:
        print("Firebase not connected")

# Save logout
def save_logout_to_cloud(email):
    if db:
        db.collection("logouts").add({
            "email": email,
            "logout_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    else:
        print("Firebase not connected")