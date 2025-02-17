"""
Authentication module providing utilities for password verification,
access token creation, and retrieving the current user from cookies.

It uses JSON Web Tokens (JWT) for authentication and Passlib for password hashing.
"""

import os
from datetime import datetime, timedelta

from fastapi import (
    HTTPException,
    Request,
    status,
)
from jose import JWTError, jwt
from passlib.context import CryptContext

# Initialize password hashing context using bcrypt.
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

# Environment configuration for JWT and admin credentials.
SECRET_KEY = os.environ.get('SECRET_KEY', 'DEV_ONLY_KEY')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise ValueError(
        'ADMIN_USERNAME and ADMIN_PASSWORD must be set in environment variables.'
    )

# Create a hashed version of the admin password.
hashed_admin_password = pwd_context.hash(ADMIN_PASSWORD)

# In-memory user database for the admin.
FAKE_USER_DB = {
    ADMIN_USERNAME: {
        'username': ADMIN_USERNAME,
        'hashed_password': hashed_admin_password,
    }
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify that the provided plain password matches the hashed password.

    Args:
        plain_password (str): The plain text password.
        hashed_password (str): The hashed password to compare against.

    Returns:
        bool: True if the password is valid, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JSON Web Token (JWT) access token.

    Args:
        data (dict): The payload data to encode in the token.
        expires_delta (timedelta, optional): Custom expiration duration.
            Defaults to ACCESS_TOKEN_EXPIRE_MINUTES if not provided.

    Returns:
        str: The encoded JWT as a string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user_from_cookie(request: Request) -> str:
    """
    Retrieve the current user's username from the access token stored in cookies.

    Args:
        request (Request): The incoming HTTP request containing cookies.

    Raises:
        HTTPException: If the access token is missing or invalid.

    Returns:
        str: The username extracted from the token.
    """
    token = request.cookies.get('access_token')
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated'
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid JWT payload'
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid JWT token'
        )
