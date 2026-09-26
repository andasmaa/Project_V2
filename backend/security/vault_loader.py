# security/vault_loader.py
import hvac
import os
from functools import lru_cache

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "root")
KV_MOUNT = "awb"

client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)

@lru_cache(maxsize=32)
def get_secret(path: str) -> dict:
    """Récupère un secret KV v2 depuis Vault"""
    try:
        response = client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point=KV_MOUNT
        )
        return response["data"]["data"]
    except Exception as e:
        print(f"⚠️ Erreur lecture Vault [{path}]: {e}")
        return {}


def get_jwt_config() -> dict:
    return get_secret("jwt")

def get_encryption_config() -> dict:
    return get_secret("encryption")

def get_database_config() -> dict:
    return get_secret("database")

def get_api_keys() -> dict:
    return get_secret("api-keys")