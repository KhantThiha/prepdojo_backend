from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings # Assuming you load your env vars here

# 1. Get the Secret from Supabase Dashboard -> Settings -> API -> JWT Secret
SUPABASE_JWT_SECRET = settings.supabase_jwt_secret 
ALGORITHM = "HS256"

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the Supabase JWT and returns the User ID if valid.
    Raises 401 if the token is invalid, expired, or missing.
    """
    token = credentials.credentials
    
    try:
        # 2. Decode the token
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=[ALGORITHM],
            options={"verify_aud": False} # Keeps it simple
        )
        
        # 3. Extract the User ID (sub = subject)
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid authentication credentials"
            )
            
        return user_id
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Could not validate credentials"
        )