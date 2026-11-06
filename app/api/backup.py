"""پشتیبان‌گیری و بازگردانی داده‌های یک دانشگاه.

GET  /backup/university/{id}/export                  -> فایل .json.gz از همه‌ی داده‌های آن دانشگاه
POST /backup/university/{id}/restore?dry_run=true    -> پیش‌نمایش (چیزی ذخیره نمی‌شود)
POST /backup/university/{id}/restore?dry_run=false   -> اعمال

بازگردانی از نوع «ادغام» است: رکوردهای فایل اضافه یا بازنویسی می‌شوند و هیچ رکوردی حذف نمی‌شود.
فقط super_admin و مدیر همان دانشگاه مجازند. جدول‌های audit_log و notifications در پشتیبان نیستند.
فایل شامل هش رمز کاربران است و باید محرمانه نگه داشته شود.
"""
import gzip
import json
import zlib
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (ثبت همه‌ی جدول‌ها در metadata)
from app.core.dependencies import get_current_user
from app.core.roles import Roles
from app.database import Base, get_db
from app.models.university import University
from app.models.user import User
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/backup", tags=["Backup"])

FORMAT = 1
MAX_UPLOAD = 100 * 1024 * 1024        # حجم فایل آپلودشده
MAX_JSON = 600 * 1024 * 1024          # حجم پس از باز کردن gzip (محافظ در برابر zip bomb)
CHUNK = 500

# ترتیب مهم است: والدین پیش از فرزندان
DIRECT = ["students", "drivers", "vehicles", "users", "stations", "routes", "contracts", "services", "schedules", "trips"]
INDIRECT = {  # جدول: (ستون پیوند, جدول والد)
    "route_stations": ("route_id", "routes"),
    "contract_drivers": ("contract_id", "contracts"),
    "contract_vehicles": ("contract_id", "contracts"),
    "contract_rates": ("contract_id", "contracts"),
    "trip_assignments": ("trip_id", "trips"),
    "trip_incidents": ("trip_id", "trips"),
    "trip_passengers": ("trip_id", "trips"),
    "station_events": ("trip_id", "trips"),
    "vehicle_locations": ("trip_id", "trips"),
    "boarding_requests": ("trip_id", "trips"),
    "feedbacks": ("trip_id", "trips"),
    "reservations": ("trip_id", "trips"),
}
ORDER = DIRECT + list(INDIRECT)
SCOPED = set(ORDER)
T = Base.metadata.tables
ADMIN_ROLES_NEEDING_SUPER = {Roles.UNIVERSITY_ADMIN, Roles.COMPANY_ADMIN}


def _where(name: str, uid: int):
    t = T[name]
    if name in INDIRECT:
        col, parent = INDIRECT[name]
        p = T[parent]
        return t.c[col].in_(select(p.c.id).where(p.c.university_id == uid))
    return t.c.university_id == uid


def _ser(v: Any) -> Any:
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        raise ValueError("ستون باینری پشتیبانی نمی‌شود")
    return v


def _conv(col, v: Any) -> Any:
    if v is None:
        return None
    try:
        pt = col.type.python_type
    except NotImplementedError:
        return v
    if pt is datetime:
        return datetime.fromisoformat(v)
    if pt is date:
        return date.fromisoformat(v)
    if pt is time:
        return time.fromisoformat(v)
    if pt is Decimal:
        return Decimal(str(v))
    if pt is bool:
        return bool(v)
    if pt is int:
        return int(v)
    if pt is float:
        return float(v)
    return v


def _check_access(db: Session, user: User, uid: int) -> University:
    if user.role == Roles.SUPER_ADMIN:
        pass
    elif user.role == Roles.UNIVERSITY_ADMIN and user.university_id == uid:
        pass
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط مدیر همین دانشگاه یا مدیر کل به پشتیبان‌گیری دسترسی دارد")
    uni = db.query(University).filter(University.id == uid).first()
    if uni is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دانشگاه پیدا نشد")
    return uni


@router.get("/university/{university_id}/export")
def export_university(university_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    uni = _check_access(db, current_user, university_id)
    tables: dict[str, list[dict]] = {}
    for name in ORDER:
        t = T[name]
        rows = db.execute(select(t).where(_where(name, university_id)).order_by(t.c.id)).mappings().all()
        tables[name] = [{c.key: _ser(r[c.key]) for c in t.c} for r in rows]
    doc = {
        "app": "hammasir", "format": FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "university": {"id": uni.id, "name": uni.name},
        "counts": {k: len(v) for k, v in tables.items()},
        "tables": tables,
    }
    data = gzip.compress(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    try:
        create_audit_log(db, user=current_user, action="backup_export", entity_type="university", entity_id=uni.id,
                         description=f"پشتیبان‌گیری از داده‌های دانشگاه {uni.name}")
        db.commit()
    except Exception:  # ثبت لاگ نباید خروجی را خراب کند
        db.rollback()
    fname = f"hammasir-backup-uni{uni.id}-{datetime.now().strftime('%Y%m%d-%H%M')}.json.gz"
    return Response(content=data, media_type="application/gzip", headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def _load_doc(raw: bytes, uid: int) -> dict:
    if raw[:2] == b"\x1f\x8b":
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            out = d.decompress(raw, MAX_JSON + 1)
        except zlib.error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "فایل پشتیبان خراب است")
        if len(out) > MAX_JSON or d.unconsumed_tail:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "فایل پشتیبان بیش از حد بزرگ است")
        raw = out
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فایل، یک پشتیبان معتبر نیست")
    if not isinstance(doc, dict) or doc.get("app") != "hammasir" or not isinstance(doc.get("tables"), dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فایل، پشتیبان هم‌مسیر نیست")
    if doc.get("format") != FORMAT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نسخه‌ی فایل پشتیبان پشتیبانی نمی‌شود")
    if (doc.get("university") or {}).get("id") != uid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این پشتیبان مربوط به دانشگاه دیگری است")
    return doc


def _existing_ids(db: Session, table: str, ids: set[int]) -> set[int]:
    t, out, lst = T[table], set(), list(ids)
    for i in range(0, len(lst), CHUNK):
        out.update(x for (x,) in db.execute(select(t.c.id).where(t.c.id.in_(lst[i:i + CHUNK]))).all())
    return out


def _apply(db: Session, uid: int, doc: dict, caller: User) -> tuple[list[dict], list[str], list[str]]:
    """اعمال داده‌ها (بدون commit). خروجی: خلاصه‌ی هر جدول، خطاها، هشدارها."""
    errors: list[str] = []
    warnings: list[str] = []
    summary: list[dict] = []
    scope_ids = {n: {x for (x,) in db.execute(select(T[n].c.id).where(_where(n, uid))).all()} for n in ORDER}
    loose_cache: dict[str, set[int]] = {}

    def err(msg: str):
        if len(errors) < 50:
            errors.append(msg)

    for name in ORDER:
        t = T[name]
        raw_rows = doc["tables"].get(name, [])
        if not isinstance(raw_rows, list):
            err(f"{name}: ساختار نامعتبر")
            continue
        rows: list[dict] = []
        skipped = 0
        for i, r in enumerate(raw_rows, start=1):
            if not isinstance(r, dict) or not isinstance(r.get("id"), int) or r["id"] <= 0:
                err(f"{name} ردیف {i}: شناسه نامعتبر")
                continue
            if name == "users":
                role = r.get("role")
                if role == Roles.SUPER_ADMIN:
                    err(f"users ردیف {i}: کاربر مدیر کل مجاز نیست")
                    continue
                if caller.role != Roles.SUPER_ADMIN and role in ADMIN_ROLES_NEEDING_SUPER:
                    skipped += 1
                    continue
            try:
                conv = {c.key: _conv(c, r[c.key]) for c in t.c if c.key in r}
            except (ValueError, TypeError, ArithmeticError):
                err(f"{name} ردیف {i}: مقدار نامعتبر")
                continue
            rows.append(conv)
        if skipped:
            warnings.append(f"{skipped} کاربر با نقش مدیر دانشگاه/شرکت در بازگردانی نادیده گرفته شد (فقط مدیر کل می‌تواند آن‌ها را بازگرداند)")
        ids = {r["id"] for r in rows}
        in_db = _existing_ids(db, name, ids)
        foreign = in_db - scope_ids[name]
        if foreign:
            err(f"{name}: شناسه‌ی {sorted(foreign)[:3]} متعلق به دانشگاه دیگری است")
            continue
        scope_ids[name] |= ids  # برای مرجع‌های هم‌جدولی (مثل trip_assignments)

        # بررسی کلیدهای خارجی
        need_loose: dict[str, set[int]] = {}
        for c in t.c:
            for fk in c.foreign_keys:
                tt = fk.column.table.name
                if tt == "universities":
                    bad = [r["id"] for r in rows if r.get(c.key) not in (None, uid) and c.key in r]
                    if bad:
                        err(f"{name}: رکورد {bad[:3]} به دانشگاه دیگری اشاره می‌کند")
                elif tt in SCOPED and tt != "users":
                    bad = [r["id"] for r in rows if r.get(c.key) is not None and r[c.key] not in scope_ids[tt]]
                    if bad:
                        err(f"{name}.{c.key}: رکورد {bad[:3]} به رکوردی خارج از این دانشگاه اشاره می‌کند")
                else:
                    need_loose.setdefault(tt, set()).update(r[c.key] for r in rows if r.get(c.key) is not None)
        for tt, vals in need_loose.items():
            known = loose_cache.setdefault(tt, set())
            miss = vals - known
            if tt == "users":
                miss -= scope_ids["users"]
            if miss:
                found = _existing_ids(db, tt, miss)
                known |= found
                if tt == "users":
                    known |= scope_ids["users"]
                lost = miss - found
                if lost:
                    err(f"{name}: ارجاع به {tt} با شناسه‌ی {sorted(lost)[:3]} که در سامانه وجود ندارد")
        if errors:
            continue

        # اعمال
        existing: dict[int, dict] = {}
        lst = sorted(in_db)
        for i in range(0, len(lst), CHUNK):
            for m in db.execute(select(t).where(t.c.id.in_(lst[i:i + CHUNK]))).mappings():
                existing[m["id"]] = dict(m)
        created = updated = unchanged = 0
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            old = existing.get(r["id"])
            if old is None:
                groups.setdefault(tuple(sorted(r)), []).append(r)
                created += 1
            elif any(old.get(k) != v for k, v in r.items() if k != "id"):
                db.execute(t.update().where(t.c.id == r["id"]).values({k: v for k, v in r.items() if k != "id"}))
                updated += 1
            else:
                unchanged += 1
        for g in groups.values():
            db.execute(t.insert(), g)
        summary.append({"table": name, "created": created, "updated": updated, "unchanged": unchanged})
    return summary, errors, warnings


def _fix_sequences(db: Session) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    for name in ORDER:
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), COALESCE((SELECT MAX(id) FROM {name}), 1))"))


@router.post("/university/{university_id}/restore")
def restore_university(
    university_id: int,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uni = _check_access(db, current_user, university_id)
    raw = file.file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "حجم فایل بیش از حد مجاز است")
    doc = _load_doc(raw, university_id)
    try:
        summary, errors, warnings = _apply(db, university_id, doc, current_user)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "بازگردانی با خطای پایگاه داده روبه‌رو شد؛ چیزی تغییر نکرد", "errors": [str(getattr(e, "orig", e))[:300]]})
    if errors:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "فایل خطا دارد؛ چیزی تغییر نکرد", "errors": errors})
    totals = {k: sum(s[k] for s in summary) for k in ("created", "updated", "unchanged")}
    if dry_run:
        db.rollback()
    else:
        try:
            _fix_sequences(db)
            create_audit_log(db, user=current_user, action="backup_restore", entity_type="university", entity_id=uni.id,
                             description=f"بازگردانی پشتیبان دانشگاه {uni.name}: {totals['created']} جدید، {totals['updated']} به‌روزشده")
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "ثبت نهایی ناموفق بود؛ چیزی تغییر نکرد", "errors": [str(getattr(e, "orig", e))[:300]]})
    return {"dry_run": dry_run, "exported_at": doc.get("exported_at"), "university": doc.get("university"), "totals": totals, "tables": summary, "warnings": warnings}
