from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_log
from app.access import member_for_user
from app.database import get_db
from app.models.models import Loan, LoanApplication, Member, MembershipApplication, User
from app.notification_events import add_admin_notification, add_notification
from app.schemas import ApplicationReview, LoanApplicationCreate, MembershipApplicationCreate
from app.security import require_admin, require_user
from app.serializers import serialize_loan_application, serialize_membership_application

router = APIRouter(prefix="/api", tags=["applications"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin-applications"])


def _next_member_id(db: Session) -> str:
    index = db.query(Member).count() + 1
    while True:
        member_id = f"MBR-{index:03d}"
        if not db.get(Member, member_id):
            return member_id
        index += 1


def _next_loan_id(db: Session) -> str:
    index = db.query(Loan).count() + 1
    while True:
        loan_id = f"LN-{index:06d}"
        if not db.get(Loan, loan_id):
            return loan_id
        index += 1


def _sync_member_loan_total(db: Session, member_id: str) -> None:
    member = db.get(Member, member_id)
    if not member:
        return
    loans = db.query(Loan).filter(Loan.member_id == member_id).all()
    member.loans = sum((loan.balance or Decimal("0") for loan in loans), Decimal("0"))


def _fmt_money(value: Decimal) -> str:
    return f"KES {int(value):,}"


@router.get("/membership/me")
def my_membership(user: User = Depends(require_user), db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.email == user.email).first()
    application = (
        db.query(MembershipApplication)
        .filter(MembershipApplication.user_id == user.id)
        .order_by(MembershipApplication.created_at.desc(), MembershipApplication.id.desc())
        .first()
    )
    return {
        "member": {"id": member.id, "status": member.status} if member else None,
        "application": serialize_membership_application(application) if application else None,
    }


@router.post("/membership/apply", status_code=status.HTTP_201_CREATED)
def apply_membership(
    payload: MembershipApplicationCreate,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if db.query(Member).filter(Member.email == user.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This account is already linked to a member")

    existing = (
        db.query(MembershipApplication)
        .filter(MembershipApplication.user_id == user.id, MembershipApplication.status == "Pending")
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A membership application is already pending")

    application = MembershipApplication(
        user_id=user.id,
        name=user.name,
        email=user.email,
        phone=payload.phone.strip(),
        national_id=payload.national_id.strip(),
        address=payload.address.strip(),
        notes=payload.notes.strip(),
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    add_admin_notification(
        db,
        title="Membership approval required",
        message=f"{application.name} submitted a membership application.",
        type="warning",
        entity_type="membership_application",
        entity_id=str(application.id),
        created_by_user_id=user.id,
    )
    write_audit_log(db, action="membership.application_submitted", entity_type="membership_application", entity_id=application.id, actor=user, request=request, after=serialize_membership_application(application))
    db.commit()
    return serialize_membership_application(application)


@router.get("/loan-applications/me")
def my_loan_applications(user: User = Depends(require_user), db: Session = Depends(get_db)):
    member = member_for_user(db, user)
    applications = (
        db.query(LoanApplication)
        .options(joinedload(LoanApplication.member))
        .filter(LoanApplication.member_id == member.id)
        .order_by(LoanApplication.created_at.desc(), LoanApplication.id.desc())
        .all()
    )
    return [serialize_loan_application(application) for application in applications]


@router.post("/loan-applications", status_code=status.HTTP_201_CREATED)
def apply_loan(
    payload: LoanApplicationCreate,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    member = member_for_user(db, user)
    if member.status != "Active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only active members can apply for loans")

    application = LoanApplication(
        user_id=user.id,
        member_id=member.id,
        amount=Decimal(str(payload.amount)),
        type=payload.type,
        purpose=payload.purpose.strip(),
        term_months=payload.term_months,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    add_admin_notification(
        db,
        title="Loan approval required",
        message=f"{member.name} requested a {payload.type} loan for {_fmt_money(application.amount)}.",
        type="warning",
        entity_type="loan_application",
        entity_id=str(application.id),
        created_by_user_id=user.id,
    )
    write_audit_log(db, action="loan.application_submitted", entity_type="loan_application", entity_id=application.id, actor=user, request=request, after=serialize_loan_application(application))
    db.commit()
    return serialize_loan_application(application)


@admin_router.get("/membership-applications")
def list_membership_applications(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    applications = (
        db.query(MembershipApplication)
        .order_by(MembershipApplication.created_at.desc(), MembershipApplication.id.desc())
        .all()
    )
    return [serialize_membership_application(application) for application in applications]


@admin_router.patch("/membership-applications/{application_id}")
def review_membership_application(
    application_id: int,
    payload: ApplicationReview,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    application = db.get(MembershipApplication, application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership application not found")
    if application.status != "Pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application has already been reviewed")

    before = serialize_membership_application(application)
    application.status = payload.status
    application.notes = payload.notes.strip()
    application.reviewed_at = datetime.utcnow()
    application.reviewed_by = admin.id

    if payload.status == "Approved":
        member = db.query(Member).filter(Member.email == application.email).first()
        if not member:
            member_id = _next_member_id(db)
            member = Member(
                id=member_id,
                user_id=application.user_id,
                name=application.name,
                email=application.email,
                savings=0,
                loans=0,
                status="Active",
                joined=date.today().isoformat(),
                shares=0,
            )
            db.add(member)
            db.flush()
        elif member.user_id is None:
            member.user_id = application.user_id
        application.member_id = member.id

    db.commit()
    db.refresh(application)
    membership_message = (
        f"Your SACCO membership was approved. Member ID: {application.member_id}."
        if application.status == "Approved"
        else f"Your SACCO membership application was rejected{': ' + application.notes if application.notes else '.'}"
    )
    add_notification(
        db,
        user_id=application.user_id,
        created_by_user_id=admin.id,
        title=f"Membership {application.status.lower()}",
        message=membership_message,
        type="success" if application.status == "Approved" else "danger",
        entity_type="membership_application",
        entity_id=str(application.id),
    )
    write_audit_log(db, action="admin.membership_application_reviewed", entity_type="membership_application", entity_id=application.id, actor=admin, request=request, before=before, after=serialize_membership_application(application))
    db.commit()
    return serialize_membership_application(application)


@admin_router.get("/loan-applications")
def list_loan_applications(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    applications = (
        db.query(LoanApplication)
        .options(joinedload(LoanApplication.member))
        .order_by(LoanApplication.created_at.desc(), LoanApplication.id.desc())
        .all()
    )
    return [serialize_loan_application(application) for application in applications]


@admin_router.patch("/loan-applications/{application_id}")
def review_loan_application(
    application_id: int,
    payload: ApplicationReview,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    application = (
        db.query(LoanApplication)
        .options(joinedload(LoanApplication.member))
        .filter(LoanApplication.id == application_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan application not found")
    if application.status != "Pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application has already been reviewed")

    before = serialize_loan_application(application)
    application.status = payload.status
    application.notes = payload.notes.strip()
    application.reviewed_at = datetime.utcnow()
    application.reviewed_by = admin.id

    if payload.status == "Approved":
        loan_id = _next_loan_id(db)

        loan = Loan(
            id=loan_id,
            member_id=application.member_id,
            amount=application.amount,
            balance=application.amount,
            rate=Decimal("12.00"),
            issued=date.today().isoformat(),
            due=(date.today() + timedelta(days=30 * application.term_months)).isoformat(),
            status="Active",
            type=application.type,
        )
        db.add(loan)
        db.flush()
        application.loan_id = loan.id
        _sync_member_loan_total(db, application.member_id)

    db.commit()
    db.refresh(application)
    loan_message = (
        f"Your {application.type} loan for {_fmt_money(application.amount)} was approved. Loan ID: {application.loan_id}."
        if application.status == "Approved"
        else f"Your {application.type} loan application was rejected{': ' + application.notes if application.notes else '.'}"
    )
    add_notification(
        db,
        user_id=application.user_id,
        created_by_user_id=admin.id,
        title=f"Loan application {application.status.lower()}",
        message=loan_message,
        type="success" if application.status == "Approved" else "danger",
        entity_type="loan_application",
        entity_id=str(application.id),
    )
    write_audit_log(db, action="admin.loan_application_reviewed", entity_type="loan_application", entity_id=application.id, actor=admin, request=request, before=before, after=serialize_loan_application(application))
    db.commit()
    return serialize_loan_application(application)
