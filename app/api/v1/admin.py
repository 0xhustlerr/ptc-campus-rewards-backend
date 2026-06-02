"""Admin management — students, wallets, ledger, catalog, rules."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession
from app.models.enums import UserStatus
from app.schemas.admin import AdminUserStatusUpdate, AuditLogRead, PendingRegistrationRead
from app.schemas.auth import UserRead
from app.schemas.earning_rule import EarningRuleCreate, EarningRuleRead, EarningRuleUpdate
from app.schemas.ledger import AdminAdjustmentRequest, AdminReversalRequest, LedgerTransactionRead
from app.schemas.reward import RewardItemCreate, RewardItemRead, RewardItemUpdate
from app.schemas.student import StudentListItem
from app.schemas.wallet import WalletRead, WalletStatusUpdate
from app.repositories.earning_rule import EarningRuleRepository
from app.repositories.reward_item import RewardItemRepository
from app.services.admin_service import AdminService
from app.services.catalog_service import CatalogService
from app.services.ledger_service import LedgerService
from app.services.student_service import StudentService
from app.services.wallet_service import WalletService
from app.utils.mappers import (
    audit_log_to_read,
    earning_rule_to_read,
    reward_item_to_read,
    student_to_list_item,
    transaction_to_read,
    pending_registration_to_read,
    user_to_read,
    wallet_to_read,
)
from app.services.user_admin_service import UserAdminService

router = APIRouter()


@router.get("/students", response_model=list[StudentListItem])
def admin_students(db: DbSession, _: AdminUser) -> list[StudentListItem]:
    wallet_svc = WalletService(db)
    return [
        student_to_list_item(s, wallet_svc.get_balance(s.wallet.id) if s.wallet else None)
        for s in StudentService(db).list_students()
    ]


@router.get("/wallets", response_model=list[WalletRead])
def admin_wallets(db: DbSession, _: AdminUser) -> list[WalletRead]:
    return [wallet_to_read(w) for w in WalletService(db).wallets.list_all()]


@router.patch("/wallets/{wallet_id}/status", response_model=WalletRead)
def update_wallet_status(
    wallet_id: UUID,
    body: WalletStatusUpdate,
    db: DbSession,
    admin: AdminUser,
) -> WalletRead:
    wallet = AdminService(db).update_wallet_status(wallet_id, body.status, actor_id=admin.id)
    return wallet_to_read(wallet)


@router.get("/transactions", response_model=list[LedgerTransactionRead])
def admin_transactions(db: DbSession, _: AdminUser) -> list[LedgerTransactionRead]:
    return [transaction_to_read(tx) for tx in LedgerService(db).list_all_transactions()]


@router.get("/audit-logs", response_model=list[AuditLogRead])
def admin_audit_logs(
    db: DbSession,
    _: AdminUser,
    limit: int = Query(100, ge=1, le=200),
) -> list[AuditLogRead]:
    return [audit_log_to_read(log) for log in AdminService(db).list_audit_logs(limit)]


@router.get("/users/pending", response_model=list[PendingRegistrationRead])
def admin_pending_users(db: DbSession, _: AdminUser) -> list[PendingRegistrationRead]:
    users = UserAdminService(db).list_pending_registrations()
    return [pending_registration_to_read(user) for user in users]


@router.patch("/users/{user_id}/status", response_model=UserRead)
def admin_update_user_status(
    user_id: UUID,
    body: AdminUserStatusUpdate,
    db: DbSession,
    admin: AdminUser,
) -> UserRead:
    user = UserAdminService(db).update_user_status(
        user_id,
        body.status,
        actor_id=admin.id,
        student_number=body.student_number,
        first_name=body.first_name,
        last_name=body.last_name,
        cohort=body.cohort,
        program=body.program,
        vendor_name=body.vendor_name,
        vendor_type=body.vendor_type,
    )
    return user_to_read(user)


@router.post("/adjustments", response_model=LedgerTransactionRead)
def admin_adjustment(
    body: AdminAdjustmentRequest, db: DbSession, admin: AdminUser
) -> LedgerTransactionRead:
    tx = AdminService(db).apply_adjustment(body, actor_id=admin.id)
    return transaction_to_read(tx)


@router.post("/reversals", response_model=LedgerTransactionRead)
def admin_reversal(body: AdminReversalRequest, db: DbSession, admin: AdminUser) -> LedgerTransactionRead:
    tx = AdminService(db).apply_reversal(body, actor_id=admin.id)
    return transaction_to_read(tx)


@router.get("/earning-rules", response_model=list[EarningRuleRead])
def list_earning_rules_admin(db: DbSession, _: AdminUser) -> list[EarningRuleRead]:
    return [earning_rule_to_read(r) for r in EarningRuleRepository(db).list_all()]


@router.get("/reward-items", response_model=list[RewardItemRead])
def list_reward_items_admin(db: DbSession, _: AdminUser) -> list[RewardItemRead]:
    return [reward_item_to_read(i) for i in RewardItemRepository(db).list_all()]


@router.post("/earning-rules", response_model=EarningRuleRead, status_code=201)
def create_earning_rule(body: EarningRuleCreate, db: DbSession, admin: AdminUser) -> EarningRuleRead:
    rule = CatalogService(db).create_earning_rule(body, actor_id=admin.id)
    return earning_rule_to_read(rule)


@router.patch("/earning-rules/{rule_id}", response_model=EarningRuleRead)
def patch_earning_rule(
    rule_id: UUID,
    body: EarningRuleUpdate,
    db: DbSession,
    admin: AdminUser,
) -> EarningRuleRead:
    rule = CatalogService(db).update_earning_rule(rule_id, body, actor_id=admin.id)
    return earning_rule_to_read(rule)


@router.post("/reward-items", response_model=RewardItemRead, status_code=201)
def create_reward_item(body: RewardItemCreate, db: DbSession, admin: AdminUser) -> RewardItemRead:
    item = CatalogService(db).create_reward_item(body, actor_id=admin.id)
    return reward_item_to_read(item)


@router.patch("/reward-items/{item_id}", response_model=RewardItemRead)
def patch_reward_item(
    item_id: UUID,
    body: RewardItemUpdate,
    db: DbSession,
    admin: AdminUser,
) -> RewardItemRead:
    item = CatalogService(db).update_reward_item(item_id, body, actor_id=admin.id)
    return reward_item_to_read(item)
