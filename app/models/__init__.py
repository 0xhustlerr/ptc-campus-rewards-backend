"""SQLAlchemy ORM models — import all for Alembic metadata registration."""

from app.models.admin_metrics import AdminMetricsSnapshot
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.earning_event import EarningEvent
from app.models.earning_rule import EarningRule
from app.models.enums import (
    AccountType,
    EarningEventStatus,
    EntryDirection,
    RedemptionStatus,
    RewardCategory,
    StaffStatus,
    StudentStatus,
    TransactionStatus,
    TransactionType,
    UserRole,
    UserStatus,
    VendorStatus,
    VendorType,
    WalletStatus,
)
from app.models.ledger import LedgerEntry, LedgerTransaction
from app.models.ledger_account import LedgerAccount
from app.models.oauth import OAuthRefreshToken
from app.models.qr_session import QRSession
from app.models.redemption import Redemption
from app.models.reward_item import RewardItem
from app.models.staff import Staff
from app.models.student import Student
from app.models.user import User
from app.models.vendor import Vendor
from app.models.wallet import Wallet

__all__ = [
    "AccountType",
    "AdminMetricsSnapshot",
    "AuditLog",
    "Base",
    "EarningEvent",
    "EarningEventStatus",
    "EarningRule",
    "EntryDirection",
    "LedgerAccount",
    "LedgerEntry",
    "LedgerTransaction",
    "OAuthRefreshToken",
    "QRSession",
    "Redemption",
    "RedemptionStatus",
    "RewardCategory",
    "RewardItem",
    "Staff",
    "StaffStatus",
    "Student",
    "StudentStatus",
    "TransactionStatus",
    "TransactionType",
    "User",
    "UserRole",
    "UserStatus",
    "Vendor",
    "VendorStatus",
    "VendorType",
    "Wallet",
    "WalletStatus",
]
