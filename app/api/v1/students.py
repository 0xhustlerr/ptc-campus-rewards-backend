"""Student profile and registration."""

from fastapi import APIRouter

from app.api.deps import AdminUser, DbSession, StaffUser, StudentUser
from app.schemas.student import StudentCreate, StudentListItem, StudentRead
from app.services.student_service import StudentService
from app.services.wallet_service import WalletService
from app.utils.mappers import student_to_list_item, student_to_read

router = APIRouter()


@router.get("/me", response_model=StudentRead)
def me(db: DbSession, user: StudentUser) -> StudentRead:
    student = StudentService(db).get_by_user_id(user.id)
    balance = None
    if student.wallet:
        balance = WalletService(db).get_balance(student.wallet.id)
    return student_to_read(student, balance)


@router.get("", response_model=list[StudentListItem])
def list_students(db: DbSession, _: StaffUser) -> list[StudentListItem]:
    wallet_svc = WalletService(db)
    return [
        student_to_list_item(
            s,
            wallet_svc.get_balance(s.wallet.id) if s.wallet else None,
        )
        for s in StudentService(db).list_students()
    ]


@router.post("", response_model=StudentRead, status_code=201)
def create_student(body: StudentCreate, db: DbSession, _: AdminUser) -> StudentRead:
    student = StudentService(db).create_student(
        email=body.email,
        password=body.password,
        student_number=body.student_number,
        first_name=body.first_name,
        last_name=body.last_name,
        cohort=body.cohort,
        program=body.program,
        phone=body.phone,
    )
    db.commit()
    balance = WalletService(db).get_balance(student.wallet.id) if student.wallet else None
    return student_to_read(student, balance)
