import re

from pydantic import BaseModel, Field, field_validator, model_validator

GMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@gmail\.com$")


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    email: str
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if len(normalized) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_gmail(cls, value: str) -> str:
        normalized = value.lower().strip()
        if not GMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Only Gmail addresses are allowed.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_upper = any(char.isupper() for char in value)
        has_lower = any(char.islower() for char in value)
        has_digit = any(char.isdigit() for char in value)
        has_special = any(not char.isalnum() for char in value)
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                "Password must include uppercase, lowercase, number, and special character."
            )
        return value

    @model_validator(mode="after")
    def validate_password_match(self) -> "SignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password do not match.")
        return self


class ResendOTPRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_gmail(cls, value: str) -> str:
        normalized = value.lower().strip()
        if not GMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Only Gmail addresses are allowed.")
        return normalized


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str = Field(..., min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def validate_gmail(cls, value: str) -> str:
        normalized = value.lower().strip()
        if not GMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Only Gmail addresses are allowed.")
        return normalized

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.isdigit():
            raise ValueError("OTP must be a 6-digit number.")
        return normalized


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_gmail(cls, value: str) -> str:
        normalized = value.lower().strip()
        if not GMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Only Gmail addresses are allowed.")
        return normalized


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, str | int | bool]


class OTPResponse(BaseModel):
    message: str
    email: str
    expires_in: int


class RegisterResponse(BaseModel):
    message: str
    email: str
    expires_in: int
