"""نرخ سفر به‌ازای نوع خودرو در هر قرارداد + گزارش هزینه.

GET    /contract-rates?contract_id=        فهرست نرخ‌ها
PUT    /contract-rates                     ثبت/ویرایش نرخ یک نوع خودرو (upsert)
DELETE /contract-rates/{id}
GET    /contract-rates/costs               هزینه = سفرهای انجام‌شده × نرخ نوع خودرو
دانشجو هیچ وجهی نمی‌پردازد؛ این هزینه تعهد دانشگاه به شرکت است.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import check_contract_access, get_current_user
from app.core.roles import Roles
from app.database import get_db
from app.models.contract import Contract
from app.models.contract_rate import ContractRate
from app.models.service import Service
from app.models.trip import Trip
from app.models.user import User
from app.models.vehicle import Vehicle

router = APIRouter(prefix="/contract-rates", tags=["Contract Rates"])

WRITE_ROLES = {Roles.SUPER_ADMIN, Roles.UNIVERSITY_ADMIN, Roles.TRANSPORT_MANAGER}
READ_ROLES = WRITE_ROLES | {Roles.COMPANY_ADMIN}


class RateIn(BaseModel):
    contract_id: int = Field(gt=0)
    vehicle_type: str = Field(min_length=1, max_length=50)
    price_per_trip: int = Field(ge=0, le=10**12)


def _contract(db: Session, user: User, contract_id: int) -> Contract:
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    check_contract_access(user, c)
    return c


def _row(r: ContractRate):
    return {"id": r.id, "contract_id": r.contract_id, "vehicle_type": r.vehicle_type, "price_per_trip": r.price_per_trip}


@router.get("")
def list_rates(contract_id: int = Query(gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in READ_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی ندارید")
    _contract(db, user, contract_id)
    rows = db.query(ContractRate).filter(ContractRate.contract_id == contract_id).order_by(ContractRate.vehicle_type).all()
    return [_row(r) for r in rows]


@router.put("")
def upsert_rate(data: RateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "شما مجوز تعیین نرخ را ندارید")
    _contract(db, user, data.contract_id)
    vt = data.vehicle_type.strip().lower()
    if not vt:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع خودرو خالی است")
    r = db.query(ContractRate).filter(ContractRate.contract_id == data.contract_id, ContractRate.vehicle_type == vt).first()
    if r is None:
        r = ContractRate(contract_id=data.contract_id, vehicle_type=vt, price_per_trip=data.price_per_trip)
        db.add(r)
    else:
        r.price_per_trip = data.price_per_trip
    db.commit()
    db.refresh(r)
    return _row(r)


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate(rate_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "شما مجوز حذف نرخ را ندارید")
    r = db.query(ContractRate).filter(ContractRate.id == rate_id).first()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نرخ پیدا نشد")
    _contract(db, user, r.contract_id)
    db.delete(r)
    db.commit()


@router.get("/costs")
def costs(
    start_date: date | None = None,
    end_date: date | None = None,
    university_id: int | None = Query(default=None, gt=0),
    transport_company_id: int | None = Query(default=None, gt=0),
    contract_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in READ_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "شما مجوز مشاهده گزارش مالی را ندارید")
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد")

    cq = db.query(Contract)
    if user.role == Roles.SUPER_ADMIN:
        if university_id:
            cq = cq.filter(Contract.university_id == university_id)
    elif user.role == Roles.COMPANY_ADMIN:
        if user.transport_company_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "حساب شما به شرکتی متصل نیست")
        cq = cq.filter(Contract.transport_company_id == user.transport_company_id)
    else:
        if user.university_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "حساب شما به دانشگاهی متصل نیست")
        cq = cq.filter(Contract.university_id == user.university_id)
    if transport_company_id:
        cq = cq.filter(Contract.transport_company_id == transport_company_id)
    if contract_id:
        cq = cq.filter(Contract.id == contract_id)
    contracts = cq.order_by(Contract.id.desc()).all()
    ids = [c.id for c in contracts]
    if not ids:
        return {"summary": {"trips": 0, "priced_trips": 0, "unpriced_trips": 0, "total_cost": 0}, "items": []}

    rates = {(r.contract_id, r.vehicle_type): r.price_per_trip
             for r in db.query(ContractRate).filter(ContractRate.contract_id.in_(ids)).all()}

    q = (db.query(Service.contract_id, Vehicle.vehicle_type, func.count(Trip.id))
         .join(Service, Service.id == Trip.service_id)
         .outerjoin(Vehicle, Vehicle.id == Trip.vehicle_id)
         .filter(Service.contract_id.in_(ids), Trip.status == "completed", Trip.is_active.is_(True)))
    if start_date:
        q = q.filter(Trip.trip_date >= start_date)
    if end_date:
        q = q.filter(Trip.trip_date <= end_date)
    counts = q.group_by(Service.contract_id, Vehicle.vehicle_type).all()

    by_contract: dict[int, list[dict]] = {}
    for cid, vtype, n in counts:
        vt = (vtype or "").strip().lower() or None
        price = rates.get((cid, vt)) if vt else None
        by_contract.setdefault(cid, []).append({
            "vehicle_type": vt, "trips": int(n), "price_per_trip": price,
            "amount": int(n) * price if price is not None else None,
        })

    items, tot = [], {"trips": 0, "priced_trips": 0, "unpriced_trips": 0, "total_cost": 0}
    for c in contracts:
        lines = sorted(by_contract.get(c.id, []), key=lambda x: x["vehicle_type"] or "")
        trips = sum(x["trips"] for x in lines)
        priced = sum(x["trips"] for x in lines if x["price_per_trip"] is not None)
        cost = sum(x["amount"] or 0 for x in lines)
        items.append({
            "contract_id": c.id, "contract_number": c.contract_number,
            "university_id": c.university_id, "transport_company_id": c.transport_company_id,
            "trips": trips, "priced_trips": priced, "unpriced_trips": trips - priced,
            "total_cost": cost, "lines": lines,
        })
        tot["trips"] += trips; tot["priced_trips"] += priced
        tot["unpriced_trips"] += trips - priced; tot["total_cost"] += cost
    return {"filters": {"start_date": start_date, "end_date": end_date}, "summary": tot, "items": items}
