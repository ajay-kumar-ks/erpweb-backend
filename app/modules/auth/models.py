from pydantic import BaseModel


class User(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None = None
    disabled: bool | None = None
    is_admin: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str
