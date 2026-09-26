# security/encryption.py
from cryptography.fernet import Fernet
import base64
import os
from security.vault_loader import get_encryption_config

# ✅ Récupère la clé depuis Vault
enc_cfg = get_encryption_config()
_key_str = enc_cfg.get("aes_key") or os.getenv("AES_ENCRYPTION_KEY")

if not _key_str:
    # ⚠️ Fallback UNIQUEMENT pour dev local si Vault n'est pas lancé
    print("⚠️ Aucune clé AES trouvée dans Vault — génération d'une clé temporaire (NON persistante)")
    _key_str = Fernet.generate_key().decode()

ENCRYPTION_KEY = _key_str.encode() if isinstance(_key_str, str) else _key_str
cipher = Fernet(ENCRYPTION_KEY)


def encrypt_sensitive_data(data: str) -> str:
    """Chiffre une donnée sensible (ex: IBAN, téléphone)"""
    if not data:
        return data
    encrypted = cipher.encrypt(data.encode())
    return base64.b64encode(encrypted).decode()


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Déchiffre une donnée sensible"""
    if not encrypted_data:
        return encrypted_data
    try:
        decoded = base64.b64decode(encrypted_data.encode())
        decrypted = cipher.decrypt(decoded)
        return decrypted.decode()
    except Exception as e:
        # Si la donnée n'était pas chiffrée (ex: ancien enregistrement)
        print(f"⚠️ Erreur déchiffrement (retour brut): {e}")
        return encrypted_data


def encrypt_client_data(client: dict) -> dict:
    """Chiffre les données sensibles d'un client"""
    client_copy = client.copy()
    if client_copy.get("iban"):
        client_copy["iban"] = encrypt_sensitive_data(client_copy["iban"])
    if client_copy.get("telephone"):
        client_copy["telephone"] = encrypt_sensitive_data(client_copy["telephone"])
    return client_copy


def decrypt_client_data(client: dict) -> dict:
    """Déchiffre les données sensibles d'un client"""
    client_copy = client.copy()
    if client_copy.get("iban"):
        client_copy["iban"] = decrypt_sensitive_data(client_copy["iban"])
    if client_copy.get("telephone"):
        client_copy["telephone"] = decrypt_sensitive_data(client_copy["telephone"])
    return client_copy