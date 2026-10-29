from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.student import Student


def get_block_days(no_show_count: int) -> int:
    if no_show_count <= 1:
        return 0

    if no_show_count == 2:
        return 1

    if no_show_count == 3:
        return 3

    if no_show_count == 4:
        return 5

    if no_show_count == 5:
        return 7

    return 14


def is_student_blocked(student: Student) -> bool:
    if student.blocked_until is None:
        return False

    now = datetime.now(timezone.utc)

    blocked_until = student.blocked_until

    if blocked_until.tzinfo is None:
        blocked_until = blocked_until.replace(tzinfo=timezone.utc)

    return blocked_until > now


def validate_student_not_blocked(
    student: Student,
) -> None:
    if not is_student_blocked(student):
        return

    blocked_until = student.blocked_until

    if blocked_until is None:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "امکان ثبت درخواست سرویس برای شما وجود ندارد. "
            f"مسدودی تا {blocked_until.isoformat()} ادامه دارد."
        ),
    )


def register_no_show(
    db: Session,
    *,
    student: Student,
) -> Student:
    student.no_show_count += 1
    student.negative_score += 1

    block_days = get_block_days(
        student.no_show_count,
    )

    if block_days > 0:
        now = datetime.now(timezone.utc)

        current_blocked_until = student.blocked_until

        if (
            current_blocked_until is not None
            and current_blocked_until.tzinfo is None
        ):
            current_blocked_until = current_blocked_until.replace(
                tzinfo=timezone.utc
            )

        if (
            current_blocked_until is not None
            and current_blocked_until > now
        ):
            base_time = current_blocked_until
        else:
            base_time = now

        student.blocked_until = (
            base_time + timedelta(days=block_days)
        )

    db.add(student)
    db.flush()

    return student