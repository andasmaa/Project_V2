# test_auth.py
import requests
import json
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

print("=" * 60)
print("🔐 TEST D'AUTHENTIFICATION")
print("=" * 60)

# Test avec Nabila Imouzas
email = "nabila.imouzaz@awb.ma"
password = "nabila20"

# Vérifier le hash localement
hash_calcule = hash_password(password)
print(f"Hash calculé pour '{password}': {hash_calcule}")
print(f"Hash dans la BD: 8f6f1476dde644c47b669c2b3c12ec46b06d723ec9afba3ff5ca86b016182213")
print(f"Match: {hash_calcule == '8f6f1476dde644c47b669c2b3c12ec46b06d723ec9afba3ff5ca86b016182213'}")

print("\n" + "=" * 60)
print("📡 TEST API LOGIN")
print("=" * 60)

try:
    response = requests.post(
        "http://localhost:8000/api/auth/login",
        json={"email": email, "password": password},
        timeout=5
    )
    print(f"Status code: {response.status_code}")
    print(f"Réponse: {response.json()}")
except requests.exceptions.ConnectionError:
    print("❌ Erreur: Le backend n'est pas lancé sur http://localhost:8000")
except Exception as e:
    print(f"❌ Erreur: {e}")