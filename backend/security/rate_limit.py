# security/rate_limit.py
from collections import defaultdict
from datetime import datetime
from fastapi import HTTPException, Request
import time

class RateLimiter:
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    async def __call__(self, request: Request):
        client_ip = request.client.host
        now = time.time()
        minute_ago = now - 60
        
        # Nettoyer les anciennes requêtes
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > minute_ago]
        
        # Vérifier la limite
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(status_code=429, detail="Trop de requêtes. Veuillez patienter.")
        
        self.requests[client_ip].append(now)

rate_limiter = RateLimiter(requests_per_minute=30)