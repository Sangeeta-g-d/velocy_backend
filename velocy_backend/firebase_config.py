import os
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIREBASE_CRED_PATH = os.path.join(BASE_DIR, "firebase_cred.json")

if not firebase_admin._apps:  # prevents multiple initialization
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)
