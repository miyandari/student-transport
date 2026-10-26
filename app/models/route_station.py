from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
)

from sqlalchemy.orm import relationship

from app.database import Base


class RouteStation(Base):
    __tablename__ = "route_stations"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    route_id = Column(
        Integer,
        ForeignKey("routes.id"),
        nullable=False,
        index=True,
    )

    station_id = Column(
        Integer,
        ForeignKey("stations.id"),
        nullable=False,
        index=True,
    )

    stop_order = Column(
        Integer,
        nullable=False,
    )

    estimated_minutes_from_start = Column(
        Integer,
        nullable=True,
    )

    stop_duration_seconds = Column(
        Integer,
        nullable=True,
    )

    # =====================================================
    # Relationships
    # =====================================================

    route = relationship(
        "Route",
        back_populates="route_stations",
        foreign_keys=[route_id],
    )

    station = relationship(
        "Station",
    )

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        UniqueConstraint(
            "route_id",
            "stop_order",
            name="uq_route_stations_route_stop_order",
        ),

        CheckConstraint(
            "route_id > 0",
            name="ck_route_stations_route_id_positive",
        ),

        CheckConstraint(
            "station_id > 0",
            name="ck_route_stations_station_id_positive",
        ),

        CheckConstraint(
            "stop_order > 0",
            name="ck_route_stations_stop_order_positive",
        ),

        CheckConstraint(
            "estimated_minutes_from_start IS NULL "
            "OR estimated_minutes_from_start >= 0",
            name="ck_route_stations_estimated_minutes_non_negative",
        ),

        CheckConstraint(
            "stop_duration_seconds IS NULL "
            "OR stop_duration_seconds >= 0",
            name="ck_route_stations_stop_duration_non_negative",
        ),

        Index(
            "ix_route_stations_route_order",
            "route_id",
            "stop_order",
        ),

        Index(
            "ix_route_stations_route_station",
            "route_id",
            "station_id",
        ),
    )