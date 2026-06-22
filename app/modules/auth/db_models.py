from sqlalchemy import Column, Integer, String, Boolean
from app.core.base import BaseModel


class User(BaseModel):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    disabled = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email}, is_admin={self.is_admin})>"
