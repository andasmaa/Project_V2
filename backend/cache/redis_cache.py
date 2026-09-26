# cache/redis_cache.py
import redis
import json
import hashlib
from typing import Optional, Dict

class CacheService:
    def __init__(self):
        self._client = None
    
    def connect(self):
        """Connexion à Redis (version simplifiée sans Redis)"""
        # Version sans Redis (cache mémoire simple)
        self._client = MemoryCache()
        print("✅ Cache mémoire activé (Redis non disponible)")
        return True
    
    def get(self, session_id: str, message: str) -> Optional[str]:
        if not self._client:
            return None
        return self._client.get(session_id, message)
    
    def set(self, session_id: str, message: str, response: str, ttl: int = 300):
        if not self._client:
            return
        self._client.set(session_id, message, response, ttl)
    
    def invalidate_session(self, session_id: str):
        if not self._client:
            return
        self._client.invalidate_session(session_id)
    
    def get_stats(self) -> Dict:
        if not self._client:
            return {"status": "disconnected"}
        return self._client.get_stats()

class MemoryCache:
    """Cache mémoire simple (fallback)"""
    
    def __init__(self):
        self._cache = {}
    
    def _get_key(self, session_id: str, message: str) -> str:
        import hashlib
        return hashlib.md5(f"{session_id}:{message}".encode()).hexdigest()
    
    def get(self, session_id: str, message: str):
        key = self._get_key(session_id, message)
        if key in self._cache:
            value, expires = self._cache[key]
            import time
            if time.time() < expires:
                return value
            del self._cache[key]
        return None
    
    def set(self, session_id: str, message: str, response: str, ttl: int = 300):
        import time
        key = self._get_key(session_id, message)
        self._cache[key] = (response, time.time() + ttl)
    
    def invalidate_session(self, session_id: str):
        keys_to_delete = [k for k in self._cache if session_id in k]
        for k in keys_to_delete:
            del self._cache[k]
    
    def get_stats(self):
        return {"status": "memory_cache", "keys_count": len(self._cache)}

# Instance unique
cache_service = CacheService()