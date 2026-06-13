from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.access import ensure_member_access, is_admin, member_for_user
from app.database import get_db
from app.models.models import Member, User
from app.pagination import page_query, paginate, per_page_query
from app.schemas import MemberCreate, MemberUpdate
from app.security import require_admin, require_user
from app.serializers import serialize_member

router = APIRouter(prefix="/api/members", tags=["members"])


@router.get("")
def get_members(
    page: int | None = page_query(),
    per_page: int | None = per_page_query(),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    query = db.query(Member).order_by(Member.id.asc())
    if not is_admin(user):
        member = member_for_user(db, user)
        query = query.filter(Member.id == member.id)

    if page is not None and per_page is not None:
        return paginate(query, page, per_page, serialize_member)

    return [serialize_member(member) for member in query.all()]


@router.get("/{member_id}")
def get_member(member_id: str, user=Depends(require_user), db: Session = Depends(get_db)):
    member = ensure_member_access(db, user, member_id)
    return serialize_member(member)


def _validate_member_user_link(db: Session, user_id: int | None, member_id: str | None = None) -> None:
    if user_id is None:
        return
    if not db.get(User, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked user not found")
    existing = db.query(Member).filter(Member.user_id == user_id).first()
    if existing and existing.id != member_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already linked to another member")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    member_id = payload.id or f"MBR-{db.query(Member).count() + 1:03d}"

    if db.get(Member, member_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Member ID already exists")
    _validate_member_user_link(db, payload.user_id)

    member = Member(
        id=member_id,
        user_id=payload.user_id,
        name=payload.name,
        email=payload.email.strip().lower(),
        savings=payload.savings,
        loans=payload.loans,
        status=payload.status,
        joined=payload.joined,
        shares=payload.shares,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    write_audit_log(db, action="admin.member_created", entity_type="member", entity_id=member.id, actor=admin, request=request, after=serialize_member(member))
    db.commit()
    return serialize_member(member)


@router.patch("/{member_id}")
def update_member(
    member_id: str,
    payload: MemberUpdate,
    request: Request,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    before = serialize_member(member)
    updates = payload.model_dump(exclude_unset=True)
    _validate_member_user_link(db, updates.get("user_id"), member_id)
    if "email" in updates and updates["email"]:
        updates["email"] = updates["email"].strip().lower()
    for key, value in updates.items():
        setattr(member, key, value)

    db.commit()
    db.refresh(member)
    write_audit_log(db, action="admin.member_updated", entity_type="member", entity_id=member.id, actor=admin, request=request, before=before, after=serialize_member(member))
    db.commit()
    return serialize_member(member)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: str, request: Request, admin=Depends(require_admin), db: Session = Depends(get_db)):
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    before = serialize_member(member)
    db.delete(member)
    write_audit_log(db, action="admin.member_deleted", entity_type="member", entity_id=member_id, actor=admin, request=request, before=before)
    db.commit()
