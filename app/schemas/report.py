from datetime import date, datetime

from pydantic import BaseModel


class TransportSummaryReport(BaseModel):
    university_id: int
    from_date: date
    to_date: date

    total_trips: int
    completed_trips: int
    cancelled_trips: int
    scheduled_trips: int

    total_reservations: int
    active_reservations: int
    waitlisted_reservations: int
    cancelled_reservations: int

    total_boarded_passengers: int
    seated_passengers: int
    standing_passengers: int
    boarding_without_reservation: int

    no_show_students: int


class FinancialReport(BaseModel):
    university_id: int
    from_date: date
    to_date: date

    active_contracts: int
    total_contract_amount: int

    total_trips: int
    completed_trips: int

    total_boarded_passengers: int
    cost_per_completed_trip: float | None
    cost_per_boarded_passenger: float | None


class RouteUsageReportItem(BaseModel):
    service_id: int
    service_name: str

    total_trips: int
    completed_trips: int
    boarded_passengers: int

    average_passengers_per_trip: float
    utilization_percent: float


class DriverPerformanceReportItem(BaseModel):
    driver_id: int
    driver_name: str

    total_trips: int
    completed_trips: int
    cancelled_trips: int

    total_boarded_passengers: int
    no_show_related_incidents: int


class VehicleUsageReportItem(BaseModel):
    vehicle_id: int
    vehicle_identifier: str

    total_trips: int
    completed_trips: int
    boarded_passengers: int

    average_passengers_per_trip: float


class ReportPeriod(BaseModel):
    from_date: date
    to_date: date

    generated_at: datetime