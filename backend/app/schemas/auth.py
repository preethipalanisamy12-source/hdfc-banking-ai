from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128
    )

class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str = Field(min_length=10, max_length=15)
    city: str = Field(min_length=2, max_length=100)    