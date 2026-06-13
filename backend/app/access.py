from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import Member, User


def is_admin(user: User) -> bool:
    return user.role == "admin"


def member_for_user(db: Session, user: User) -> Member:
    member = db.query(Member).filter(Member.user_id == user.id).first()
    if not member:
        member = db.query(Member).filter(Member.email == user.email).first()
        if member and member.user_id is None:
            member.user_id = user.id
            db.commit()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No member record is linked to this user account",
        )
    return member


def ensure_member_access(db: Session, user: User, member_id: str) -> Member:
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if is_admin(user) or member.user_id == user.id or (member.user_id is None and member.email == user.email):
        return member

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own member record")
