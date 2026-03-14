import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.join(BASE_DIR, "firebase_keys.json"))
    firebase_admin.initialize_app(cred)

db = firestore.client()


def save_login_to_cloud(email):
    db.collection("logins").add({
        "email": email,
        "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


def save_logout_to_cloud(email):
    db.collection("logouts").add({
        "email": email,
        "logout_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    import firebase_admin
from firebase_admin import credentials, firestore
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.join(BASE_DIR, "firebase_keys.json"))
    firebase_admin.initialize_app(cred)

db = firestore.client()