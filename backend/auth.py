from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# In production, this would be loaded from environment variables
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "b3c959728bde4cf08bfb29ef5ce111a43a0591f09c6cd77f6b92a4bdce4ea462")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    import hashlib
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == hashed_password


def get_password_hash(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
