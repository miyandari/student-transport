from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Route(Base):
    __tablename__ = "routes"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    university_id = Column(
        Integer,
        ForeignKey("universities.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    code = Column(
        String(50),
        nullable=False,
        index=True,
    )

    direction = Column(
        String(20),
        nullable=False,
    )

    description = Column(
        String(1000),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # =====================================================
    # Relationships
    # =====================================================

    university = relationship(
        "University",
    )

    route_stations = relationship(
        "RouteStation",
        back_populates="route",
        foreign_keys="RouteStation.route_id",
        cascade="all, delete-orphan",
    )

    services = relationship(
        "Service",
        back_populates="route",
        foreign_keys="Service.route_id",
    )

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_routes_university_id_positive",
        ),

        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_routes_name_not_empty",
        ),

        CheckConstraint(
            "length(trim(code)) > 0",
            name="ck_routes_code_not_empty",
        ),

        CheckConstraint(
            "length(trim(direction)) > 0",
            name="ck_routes_direction_not_empty",
        ),

        CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_routes_description_not_empty",
        ),

        Index(
            "ix_routes_university_active",
            "university_id",
            "is_active",
        ),

        Index(
            "ix_routes_university_code",
            "university_id",
            "code",
        ),
    )