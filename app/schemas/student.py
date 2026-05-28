from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import StudentStatus
from app.schemas.common import ORMModel


class StudentCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    student_number: str
    first_name: str
    last_name: str
    cohort: str | None = None
    program: str | None = None
    phone: str | None = None


class StudentRead(ORMModel):
    id: UUID
    user_id: UUID
    student_number: str
    first_name: str
    last_name: str
    cohort: str | None
    program: str | None
    status: StudentStatus
    email: str | None = None
    wallet_id: UUID | None = None
    balance: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class StudentListItem(ORMModel):
    id: UUID
    student_number: str
    first_name: str
    last_name: str
    cohort: str | None
    program: str | None
    status: StudentStatus
    wallet_id: UUID | None = None
    balance: Decimal | None = None
