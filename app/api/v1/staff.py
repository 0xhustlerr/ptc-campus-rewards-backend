"""Staff operations — issue PTC Credits."""

from fastapi import APIRouter

from app.api.deps import DbSession, StaffUser
from app.schemas.ledger import IssueRewardRequest, IssueRewardResponse
from app.schemas.student import StudentListItem
from app.services.earning_service import EarningService
from app.services.student_service import StudentService
from app.services.wallet_service import WalletService
from app.utils.mappers import student_to_list_item

router = APIRouter()


@router.get("/students", response_model=list[StudentListItem])
def staff_list_students(db: DbSession, _: StaffUser) -> list[StudentListItem]:
    wallet_svc = WalletService(db)
    return [
        student_to_list_item(s, wallet_svc.get_balance(s.wallet.id) if s.wallet else None)
        for s in StudentService(db).list_students()
    ]


@router.post("/issue-reward", response_model=IssueRewardResponse)
def issue_reward(body: IssueRewardRequest, db: DbSession, staff: StaffUser) -> IssueRewardResponse:
    event = EarningService(db).issue_reward(
        student_id=body.student_id,
        earning_rule_id=body.earning_rule_id,
        notes=body.notes,
        idempotency_key=body.idempotency_key,
        issued_by=staff.id,
    )
    student = StudentService(db).get_by_id(body.student_id)
    balance = WalletService(db).get_balance(student.wallet.id) if student.wallet else 0
    return IssueRewardResponse(
        earning_event_id=event.id,
        ledger_transaction_id=event.ledger_transaction_id,
        amount=event.amount,
        new_balance=balance,
        status=event.status.value,
    )
