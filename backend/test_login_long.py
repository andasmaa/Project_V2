import requests
import time

print("🔐 Test de connexion...")
start = time.time()

try:
    response = requests.post(
        "http://localhost:8000/api/auth/login",
        json={"email": "nabila.imouzaz@awb.ma", "password": "nabila20"},
        timeout=30
    )
    elapsed = time.time() - start
    print(f"✅ Réponse reçue en {elapsed:.2f} secondes")
    print(f"Status: {response.status_code}")
    print(f"Réponse: {response.json()}")
    
    if response.status_code == 200 and response.json().get("success"):
        session_id = response.json()["session_id"]
        print(f"\n🔑 Session ID: {session_id}")
        
        # Test du chat
        print("\n💬 Test du chat...")
        chat_response = requests.post(
            "http://localhost:8000/chat",
            json={
                "message": "Quel est le solde de mon compte courant ?",
                "history": [],
                "session_id": session_id
            },
            timeout=30
        )
        print(f"Réponse chat: {chat_response.json()}")
        
except requests.exceptions.Timeout:
    print("❌ Timeout - Le serveur met trop de temps à répondre")
except Exception as e:
    print(f"❌ Erreur: {e}")