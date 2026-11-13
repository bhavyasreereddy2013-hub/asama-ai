from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("password")
    @classmethod
    def password_must_fit_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BusinessProfileCreate(BaseModel):
    company_name: str
    industry: str
    description: str = ""
    products: str = ""
    services: str = ""
    location: str = ""
    requirements: str = ""
    interests: str = ""


class AgentCreate(BaseModel):
    name: str
    industry: str
    summary: str = ""
    business_goals: str = ""
    interests: str = ""
    location: str = ""


class PostCreate(BaseModel):
    agent_id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    category: str = Field(default="General", max_length=255)
    requirements: str = Field(default="", max_length=2000)

    @field_validator("title", "description")
    @classmethod
    def post_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class PostUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    category: str = Field(default="General", max_length=255)
    requirements: str = Field(default="", max_length=2000)

    @field_validator("title", "description")
    @classmethod
    def post_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class ConnectionRequestCreate(BaseModel):
    receiver_id: int
    note: str = Field(default="", max_length=1000)


class ConnectionRequestResponse(BaseModel):
    status: Literal["accepted", "rejected"]


class MessageCreate(BaseModel):
    receiver_id: int
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def body_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    industry: str | None = None
    location: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Search query cannot be blank")
        return value

    @field_validator("industry", "location")
    @classmethod
    def normalize_filter(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessProfileOut(BaseModel):
    id: int
    user_id: int
    company_name: str
    industry: str
    description: str
    products: str
    services: str
    location: str
    requirements: str
    interests: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentOut(BaseModel):
    id: int
    user_id: int
    name: str
    industry: str
    summary: str
    business_goals: str
    interests: str
    location: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostOut(BaseModel):
    id: int
    agent_id: int
    title: str
    description: str
    category: str
    requirements: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
