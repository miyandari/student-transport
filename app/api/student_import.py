"""بارگذاری گروهی دانشجویان (پیش‌نمایش + ثبت نهایی).

POST /student-import
  - dry_run=true  : فقط اعتبارسنجی؛ چیزی ذخیره نمی‌شود.
  - dry_run=false : تمام ردیف‌ها یا هیچ‌کدام (در صورت وجود خطا 400).
برای هر دانشجو یک حساب کاربری با نام‌کاربری = شماره دانشجویی ساخته می‌شود.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import Roles
from app.core.security import hash_password
from app.database import get_db
from app.models.student import Student
from app.models.university import University
from app.models.user import User
from app.services.student_qr_service import ensure_student_qr_token

router = APIRouter(prefix="/student-import", tags=["Student Import"])

MAX_ROWS = 5000
GENDER_MAP = {
    "male": "male", "m": "male", "مرد": "male", "آقا": "male", "پسر": "male",
    "female": "female", "f": "female", "زن": "female", "خانم": "female", "دختر": "female",
}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class ImportRow(BaseModel):
    student_number: str = ""
    first_name: str = ""
    last_name: str = ""
    gender: str = ""
    national_id: str | None = None
    phone: str | None = None


class ImportRequest(BaseModel):
    university_id: int
    rows: list[ImportRow] = Field(max_length=MAX_ROWS)
    initial_password: str = Field(min_length=8, max_length=64)
    dry_run: bool = True


def _clean(v: str | None) -> str:
    return (v or "").translate(_DIGITS).strip()


@router.post("")
def import_students(
    data: ImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (Roles.SUPER_ADMIN, Roles.UNIVERSITY_ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "شما مجوز بارگذاری دانشجو را ندارید")
    if current_user.role == Roles.UNIVERSITY_ADMIN and current_user.university_id != data.university_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این دانشگاه ندارید")
    uni = db.query(University).filter(University.id == data.university_id, University.is_active.is_(True)).first()
    if uni is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دانشگاه پیدا نشد")

    nums = [_clean(r.student_number) for r in data.rows]
    nids = [_clean(r.national_id) for r in data.rows if _clean(r.national_id)]
    ex_nums = {n for (n,) in db.query(Student.student_number).filter(
        Student.university_id == data.university_id, Student.student_number.in_(nums)).all()}
    ex_users = {u for (u,) in db.query(User.username).filter(User.username.in_(nums)).all()}
    ex_nids = {n for (n,) in db.query(Student.national_id).filter(Student.national_id.in_(nids)).all()} if nids else set()

    seen_nums: set[str] = set()
    seen_nids: set[str] = set()
    results, valid = [], []
    for i, r in enumerate(data.rows, start=1):
        num, fn, ln = _clean(r.student_number), _clean(r.first_name), _clean(r.last_name)
        gender = GENDER_MAP.get(_clean(r.gender).lower())
        nid, phone = _clean(r.national_id) or None, _clean(r.phone) or None
        errs = []
        if not num:
            errs.append("شماره دانشجویی خالی است")
        elif num in seen_nums:
            errs.append("شماره دانشجویی تکراری در فایل")
        elif num in ex_nums or num in ex_users:
            errs.append("شماره دانشجویی قبلاً ثبت شده")
        if not fn or not ln:
            errs.append("نام یا نام خانوادگی خالی است")
        if gender is None:
            errs.append("جنسیت نامعتبر (مرد/زن)")
        if nid:
            if nid in seen_nids:
                errs.append("کد ملی تکراری در فایل")
            elif nid in ex_nids:
                errs.append("کد ملی قبلاً ثبت شده")
            seen_nids.add(nid)
        if num:
            seen_nums.add(num)
        results.append({"row": i, "student_number": num, "ok": not errs, "errors": errs})
        if not errs:
            valid.append((num, fn, ln, gender, nid, phone))

    bad = sum(1 for x in results if not x["ok"])
    summary = {"total": len(results), "valid": len(valid), "invalid": bad, "dry_run": data.dry_run}
    if data.dry_run:
        return {**summary, "results": results}
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "فایل خطا دارد؛ هیچ دانشجویی ثبت نشد", **summary, "results": results})

    pw_hash = hash_password(data.initial_password)
    try:
        for num, fn, ln, gender, nid, phone in valid:
            s = Student(university_id=data.university_id, student_number=num, first_name=fn,
                        last_name=ln, gender=gender, national_id=nid, phone=phone, is_active=True)
            db.add(s)
            db.flush()
            ensure_student_qr_token(db, s)
            db.add(User(university_id=data.university_id, student_id=s.id, username=num,
                        password_hash=pw_hash, first_name=fn, last_name=ln, phone=phone,
                        role=Roles.STUDENT, is_active=True))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {**summary, "created": len(valid)}
