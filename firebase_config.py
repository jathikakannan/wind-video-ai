import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Path to project root (where manage.py is)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIREBASE_PATH = os.path.join(BASE_DIR, "firebase_keys.json")

# Initialize Firebase safely
if not firebase_admin._apps:
    if os.path.exists(FIREBASE_PATH):
        cred = credentials.Certificate(FIREBASE_PATH)
        firebase_admin.initialize_app(cred)
    else:
        print(f"⚠️ Firebase JSON not found at {FIREBASE_PATH}")
        db = None

db = firestore.client() if firebase_admin._apps else None

# Functions to save login/logout
def save_login_to_cloud(email):
    if db:
        db.collection("logins").add({
            "email": email,
            "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

def save_logout_to_cloud(email):
    if db:
        db.collection("logouts").add({
            "email": email,
            "logout_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })