import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.vendor import Vendor


class VendorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        stmt = select(Vendor).options(joinedload(Vendor.user)).where(Vendor.id == vendor_id)
        return self.db.scalars(stmt).first()

    def get_by_user_id(self, user_id: uuid.UUID) -> Vendor | None:
        stmt = select(Vendor).options(joinedload(Vendor.user)).where(Vendor.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create(self, vendor: Vendor) -> Vendor:
        self.db.add(vendor)
        self.db.flush()
        return vendor
