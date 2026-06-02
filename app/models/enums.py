"""Shared enumerations for ORM models."""

import enum


class UserRole(str, enum.Enum):
    student = "student"
    staff = "staff"
    vendor = "vendor"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    pending = "pending"
    inactive = "inactive"
    suspended = "suspended"


class StudentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    graduated = "graduated"
    withdrawn = "withdrawn"


class StaffStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class VendorType(str, enum.Enum):
    food_truck = "food_truck"
    school_store = "school_store"
    campus_perk = "campus_perk"


class VendorStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class WalletStatus(str, enum.Enum):
    active = "active"
    frozen = "frozen"
    closed = "closed"


class AccountType(str, enum.Enum):
    student_wallet = "student_wallet"
    rewards_pool = "rewards_pool"
    vendor_revenue = "vendor_revenue"
    system_adjustment = "system_adjustment"


class TransactionType(str, enum.Enum):
    earn = "earn"
    redeem = "redeem"
    bonus = "bonus"
    reversal = "reversal"
    adjustment = "adjustment"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    posted = "posted"
    failed = "failed"
    reversed = "reversed"


class EntryDirection(str, enum.Enum):
    debit = "debit"
    credit = "credit"


class EarningEventStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    posted = "posted"
    reversed = "reversed"


class RewardCategory(str, enum.Enum):
    food_truck = "food_truck"
    school_supplies = "school_supplies"
    student_perks = "student_perks"


class RedemptionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    reversed = "reversed"
