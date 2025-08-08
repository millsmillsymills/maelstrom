from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv


load_dotenv()  # Load API_KEY from .env if present

bearer_scheme = HTTPBearer(auto_error=False)


def _get_api_key() -> Optional[str]:
    return os.getenv("API_KEY")


def api_key_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    api_key = _get_api_key()
    if not api_key:
        # If no key configured, block access by default
        raise HTTPException(status_code=503, detail="API not configured: missing API_KEY")
    if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

