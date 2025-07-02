from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int

    class Config:
        from_attributes = True


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ArticleBase(BaseModel):
    code: str


class ArticleCreate(ArticleBase):
    pass


class Article(ArticleBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


class SupplierBase(BaseModel):
    name: str
    website: str
    email: Optional[str] = None
    country: Optional[str] = None


class SupplierCreate(SupplierBase):
    article_id: int


class Supplier(SupplierBase):
    id: int
    article_id: int
    contact_date: Optional[datetime] = None
    status: Optional[str] = "new"

    class Config:
        from_attributes = True


class EmailTemplateBase(BaseModel):
    name: str
    subject: str
    body: str


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplate(EmailTemplateBase):
    id: int

    class Config:
        from_attributes = True


class SentEmailBase(BaseModel):
    supplier_id: int
    template_id: int
    sender_email: str


class SentEmailCreate(SentEmailBase):
    pass


class SentEmail(SentEmailBase):
    id: int
    sent_at: datetime
    status: str
    error: Optional[str] = None

    class Config:
        from_attributes = True