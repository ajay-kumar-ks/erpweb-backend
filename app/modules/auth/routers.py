from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.core.config import settings
from app.core.database import get_db
from app.modules.auth.schemas import LoginRequest, LoginResponse
from app.modules.auth.models import User
from app.modules.auth.db_models import User as UserDB
from app.modules.auth.utils import verify_password, create_access_token

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(UserDB).filter(UserDB.username == username).first()
    if not user:
        raise credentials_exception
    return User(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        is_admin=user.is_admin,
    )


def authenticate_user(username: str, password: str, db: Session) -> User | None:
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return User(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        is_admin=user.is_admin,
    )


@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(login_data.username, login_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users")
async def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    users = db.query(UserDB).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
        }
        for u in users
    ]


@router.get("/dashboard")
async def dashboard(current_user: User = Depends(get_current_user)):
    return {
        "message": "Welcome to your dashboard",
        "user": {
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "is_admin": current_user.is_admin,
        },
    }

