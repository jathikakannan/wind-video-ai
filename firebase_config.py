import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Path to project root (where manage.py is located)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIREBASE_PATH = os.path.join(BASE_DIR, "firebase_keys.json")

db = None

try:
    # Initialize Firebase only once
    if not firebase_admin._apps:
        if os.path.exists(FIREBASE_PATH):
            cred = credentials.Certificate(FIREBASE_PATH)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase initialized successfully")
        else:
            print(f"⚠️ Firebase JSON not found at {FIREBASE_PATH}")

    # Initialize Firestore only if Firebase app exists
    if firebase_admin._apps:
        db = firestore.client()

except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    db = None


# Function to save login event
def save_login_to_cloud(email):
    if db:
        try:
            db.collection("logins").add({
                "email": email,
                "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            print(f"Login save error: {e}")


# Function to save logout event
def save_logout_to_cloud(email):
    if db:
        try:
            db.collection("logouts").add({
                "email": email,
                "logout_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            print(f"Logout save error: {e}")