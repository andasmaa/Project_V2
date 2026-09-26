# security/auth.py
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from security.vault_loader import get_jwt_config
import os

jwt_cfg = get_jwt_config()

SECRET_KEY = jwt_cfg.get("secret_key") or os.getenv("JWT_SECRET_KEY", "fallback_dev_key")
ALGORITHM = jwt_cfg.get("algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(jwt_cfg.get("access_token_expire_minutes", 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(jwt_cfg.get("refresh_token_expire_days", 7))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Rôles utilisateurs
class UserRole:
    CLIENT = "client"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"

# Base de données utilisateurs (à étendre dans ta BD)
USER_ROLES = {
    "nabila.imouzas@awb.ma": UserRole.CLIENT,
    "supervisor@awb.ma": UserRole.SUPERVISOR,
    "admin@awb.ma": UserRole.ADMIN,
}

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: Dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict:
    token = credentials.credentials
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token invalide")
    return payload

def require_role(required_role: str):
    def role_checker(current_user: Dict = Depends(get_current_user)):
        if current_user.get("role") != required_role and current_user.get("role") != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail=f"Rôle {required_role} requis")
        return current_user
    return role_checker