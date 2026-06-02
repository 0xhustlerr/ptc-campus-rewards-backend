"""
Seed development login accounts (local / dev only).

Usage:
  python -m scripts.seed_users

Creates one user per role if the email does not already exist.
"""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus, VendorStatus, VendorType
from app.models.user import User
from app.models.vendor import Vendor
from app.repositories.user import UserRepository
from app.repositories.vendor import VendorRepository
from app.services.staff_service import StaffService
from app.services.student_service import StudentService
from app.services.system_accounts_service import SystemAccountsService

# Dev-only credentials — change in production; never use in deployed environments.
DEV_PASSWORD = "CampusDev123!"

DEV_USERS: list[dict] = [
    {
        "email": "admin@ptc.edu",
        "role": UserRole.admin,
        "label": "Admin",
    },
    {
        "email": "staff@ptc.edu",
        "role": UserRole.staff,
        "label": "Staff",
        "first_name": "Campus",
        "last_name": "Staff",
        "department": "Student Services",
    },
    {
        "email": "student@ptc.edu",
        "role": UserRole.student,
        "label": "Student",
        "student_number": "PTC-0001",
        "first_name": "Arlo",
        "last_name": "Jr",
        "cohort": "2026-A",
        "program": "Barbering",
    },
    {
        "email": "vendor@ptc.edu",
        "role": UserRole.vendor,
        "label": "Vendor",
        "vendor_name": "Campus Court Food Truck",
        "vendor_type": VendorType.food_truck,
    },
]


def _ensure_simple_user(db, users: UserRepository, spec: dict) -> User | None:
    existing = users.get_by_email(spec["email"])
    if existing:
        print(f"  skip {spec['label']}: {spec['email']} (already exists)")
        return existing

    user = User(
        email=spec["email"],
        hashed_password=hash_password(DEV_PASSWORD),
        role=spec["role"],
        status=UserStatus.active,
    )
    users.create(user)
    print(f"  created {spec['label']}: {spec['email']}")
    return user


def seed_dev_users() -> None:
    db = SessionLocal()
    try:
        SystemAccountsService(db).ensure_system_accounts()
        users = UserRepository(db)
        student_svc = StudentService(db)
        staff_svc = StaffService(db)

        print("Seeding development users (password for all new accounts: CampusDev123!)")
        for spec in DEV_USERS:
            role = spec["role"]
            if role == UserRole.staff:
                if users.get_by_email(spec["email"]):
                    print(f"  skip Staff: {spec['email']} (already exists)")
                    continue
                staff_svc.create_staff(
                    email=spec["email"],
                    password=DEV_PASSWORD,
                    first_name=spec["first_name"],
                    last_name=spec["last_name"],
                    department=spec.get("department"),
                )
                print(f"  created Staff: {spec['email']}")
                continue

            if role == UserRole.student:
                if users.get_by_email(spec["email"]):
                    print(f"  skip Student: {spec['email']} (already exists)")
                    continue
                student_svc.create_student(
                    email=spec["email"],
                    password=DEV_PASSWORD,
                    student_number=spec["student_number"],
                    first_name=spec["first_name"],
                    last_name=spec["last_name"],
                    cohort=spec.get("cohort"),
                    program=spec.get("program"),
                )
                print(f"  created Student: {spec['email']} (wallet included)")
                continue

            if role == UserRole.vendor:
                if users.get_by_email(spec["email"]):
                    print(f"  skip Vendor: {spec['email']} (already exists)")
                    continue
                user = User(
                    email=spec["email"],
                    hashed_password=hash_password(DEV_PASSWORD),
                    role=UserRole.vendor,
                    status=UserStatus.active,
                )
                users.create(user)
                vendor = Vendor(
                    user_id=user.id,
                    name=spec["vendor_name"],
                    vendor_type=spec["vendor_type"],
                    status=VendorStatus.active,
                )
                VendorRepository(db).create(vendor)
                SystemAccountsService(db).ensure_vendor_account(vendor.id, vendor.name)
                print(f"  created Vendor: {spec['email']}")
                continue

            _ensure_simple_user(db, users, spec)

        db.commit()
        print("Dev user seed completed.")
        print("Sign in at http://localhost:3000/login with any seeded email and password: CampusDev123!")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_dev_users()
