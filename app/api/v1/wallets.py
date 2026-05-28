"""Wallet balance, QR sessions, and transaction history."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, StudentUser, require_own_wallet
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.schemas.ledger import LedgerTransactionRead, QRSessionResponse
from app.schemas.wallet import WalletBalanceRead, WalletMeRead
from app.services.redemption_service import RedemptionService
from app.services.student_service import StudentService
from app.services.wallet_service import WalletService
from app.utils.mappers import transaction_to_read
from app.utils.pagination import PaginatedResponse, PaginationParams, pagination_params

router = APIRouter()
settings = get_settings()


@router.get("/me", response_model=WalletMeRead)
def my_wallet(db: DbSession, user: StudentUser) -> WalletMeRead:
    student = StudentService(db).get_by_user_id(user.id)
    wallet = student.wallet
    if not wallet:
        raise NotFoundError("Wallet not found")
    balance = WalletService(db).get_balance(wallet.id)
    return WalletMeRead(
        wallet_id=wallet.id,
        student_id=student.id,
        student_name=student.full_name,
        student_number=student.student_number,
        currency_code=wallet.currency_code,
        balance=balance,
        status=wallet.status,
    )


@router.post("/me/qr-session", response_model=QRSessionResponse)
def create_my_qr_session(db: DbSession, user: StudentUser) -> QRSessionResponse:
    """Generate a single-use QR session token. Only the hash is stored server-side."""
    student = StudentService(db).get_by_user_id(user.id)
    plain, session = RedemptionService(db).create_qr_session(student.id)
    return QRSessionResponse(
        qr_session_token=plain,
        expires_at=session.expires_at.isoformat(),
        ttl_seconds=settings.qr_session_ttl_seconds,
    )


@router.get("/{wallet_id}/balance", response_model=WalletBalanceRead)
def wallet_balance(wallet_id: UUID, db: DbSession, user: CurrentUser) -> WalletBalanceRead:
    require_own_wallet(wallet_id, user, db)
    wallet_svc = WalletService(db)
    wallet = wallet_svc.wallets.get_by_id(wallet_id)
    if not wallet:
        raise NotFoundError("Wallet not found")
    return WalletBalanceRead(
        wallet_id=wallet_id,
        currency_code=wallet.currency_code,
        balance=wallet_svc.get_balance(wallet_id),
        status=wallet.status,
    )


@router.get("/{wallet_id}/transactions", response_model=PaginatedResponse[LedgerTransactionRead])
def wallet_transactions(
    wallet_id: UUID,
    db: DbSession,
    user: CurrentUser,
    pagination: PaginationParams = Depends(pagination_params),
) -> PaginatedResponse[LedgerTransactionRead]:
    require_own_wallet(wallet_id, user, db)
    wallet_svc = WalletService(db)
    txs = wallet_svc.list_transactions(
        wallet_id, limit=pagination.limit, offset=pagination.offset
    )
    total = wallet_svc.count_transactions(wallet_id)
    return PaginatedResponse.create(
        [transaction_to_read(tx) for tx in txs],
        total,
        pagination,
    )
