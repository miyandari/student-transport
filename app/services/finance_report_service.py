from datetime import date

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.service import Service
from app.models.trip import Trip
from app.models.university import University
from app.models.transport_company import TransportCompany


COMPLETED_TRIP_STATUS = "completed"


def get_finance_report(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    university_id: int | None = None,
    transport_company_id: int | None = None,
    contract_id: int | None = None,
):
    trip_conditions = [
        Trip.service_id == Service.id,
        Trip.status == COMPLETED_TRIP_STATUS,
        Trip.is_active.is_(True),
    ]

    if start_date is not None:
        trip_conditions.append(Trip.trip_date >= start_date)

    if end_date is not None:
        trip_conditions.append(Trip.trip_date <= end_date)

    query = (
        db.query(
            Contract.id.label("contract_id"),
            Contract.contract_number.label("contract_number"),
            Contract.start_date.label("contract_start_date"),
            Contract.end_date.label("contract_end_date"),
            Contract.contract_amount.label("contract_amount"),
            Contract.is_active.label("contract_is_active"),
            University.id.label("university_id"),
            University.name.label("university_name"),
            TransportCompany.id.label("transport_company_id"),
            TransportCompany.name.label("transport_company_name"),
            func.count(func.distinct(Service.id)).label("service_count"),
            func.count(func.distinct(Trip.id)).label("completed_trip_count"),
        )
        .join(
            University,
            University.id == Contract.university_id,
        )
        .join(
            TransportCompany,
            TransportCompany.id == Contract.transport_company_id,
        )
        .outerjoin(
            Service,
            Service.contract_id == Contract.id,
        )
        .outerjoin(
            Trip,
            and_(*trip_conditions),
        )
        .filter(
            Contract.is_active.is_(True),
        )
    )

    if university_id is not None:
        query = query.filter(
            Contract.university_id == university_id,
        )

    if transport_company_id is not None:
        query = query.filter(
            Contract.transport_company_id == transport_company_id,
        )

    if contract_id is not None:
        query = query.filter(
            Contract.id == contract_id,
        )

    query = (
        query.group_by(
            Contract.id,
            Contract.contract_number,
            Contract.start_date,
            Contract.end_date,
            Contract.contract_amount,
            Contract.is_active,
            University.id,
            University.name,
            TransportCompany.id,
            TransportCompany.name,
        )
        .order_by(
            Contract.id.desc(),
        )
    )

    rows = query.all()

    result = []

    total_contract_amount = 0
    total_completed_trips = 0
    total_services = 0

    for row in rows:
        contract_amount = (
            int(row.contract_amount)
            if row.contract_amount is not None
            else 0
        )

        completed_trip_count = int(
            row.completed_trip_count or 0
        )

        service_count = int(
            row.service_count or 0
        )

        total_contract_amount += contract_amount
        total_completed_trips += completed_trip_count
        total_services += service_count

        result.append(
            {
                "contract_id": row.contract_id,
                "contract_number": row.contract_number,
                "contract_start_date": row.contract_start_date,
                "contract_end_date": row.contract_end_date,
                "contract_amount": contract_amount,
                "university_id": row.university_id,
                "university_name": row.university_name,
                "transport_company_id": row.transport_company_id,
                "transport_company_name": row.transport_company_name,
                "service_count": service_count,
                "completed_trip_count": completed_trip_count,
            }
        )

    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "university_id": university_id,
            "transport_company_id": transport_company_id,
            "contract_id": contract_id,
        },
        "summary": {
            "contract_count": len(result),
            "service_count": total_services,
            "completed_trip_count": total_completed_trips,
            "total_contract_amount": total_contract_amount,
        },
        "items": result,
    }


def get_contract_finance_summary(
    db: Session,
    *,
    contract_id: int,
):
    report = get_finance_report(
        db,
        contract_id=contract_id,
    )

    if not report["items"]:
        return None

    return report["items"][0]


def get_university_finance_summary(
    db: Session,
    *,
    university_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
):
    report = get_finance_report(
        db,
        university_id=university_id,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "university_id": university_id,
        "start_date": start_date,
        "end_date": end_date,
        "summary": report["summary"],
        "items": report["items"],
    }


def get_transport_company_finance_summary(
    db: Session,
    *,
    transport_company_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
):
    report = get_finance_report(
        db,
        transport_company_id=transport_company_id,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "transport_company_id": transport_company_id,
        "start_date": start_date,
        "end_date": end_date,
        "summary": report["summary"],
        "items": report["items"],
    }