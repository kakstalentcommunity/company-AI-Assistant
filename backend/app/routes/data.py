from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.access import is_admin, member_for_user
from app.database import DATABASE_URL, get_db
from app.models.models import AnomalyFlag, Loan, Member, MemberProfile, PortfolioSnapshot, Transaction
from app.security import require_user
from app.serializers import (
    build_portfolio_growth,
    build_loan_distribution,
    serialize_anomaly_flags,
    serialize_loan,
    serialize_member,
    serialize_member_profile,
    serialize_portfolio_snapshot,
    serialize_transaction,
)
from app.services.fraud import sync_anomaly_flags

router = APIRouter(prefix="/api", tags=["sacco-data"])


def _load_sacco_data(db: Session, user) -> dict:
    sync_anomaly_flags(db)

    if is_admin(user):
        members = db.query(Member).order_by(Member.id.asc()).all()
        loans = db.query(Loan).order_by(Loan.issued.desc(), Loan.id.desc()).all()
        transactions = db.query(Transaction).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        portfolio = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.id.asc()).all()
        profiles = db.query(MemberProfile).order_by(MemberProfile.member_id.asc()).all()
        flags = db.query(AnomalyFlag).order_by(AnomalyFlag.transaction_id.asc()).all()
    else:
        member = member_for_user(db, user)
        members = [member]
        loans = db.query(Loan).filter(Loan.member_id == member.id).order_by(Loan.issued.desc(), Loan.id.desc()).all()
        transactions = (
            db.query(Transaction)
            .filter(Transaction.member_id == member.id)
            .order_by(Transaction.date.desc(), Transaction.id.desc())
            .all()
        )
        portfolio = []
        profiles = db.query(MemberProfile).filter(MemberProfile.member_id == member.id).all()
        transaction_ids = [transaction.id for transaction in transactions]
        flags = (
            db.query(AnomalyFlag)
            .filter(AnomalyFlag.transaction_id.in_(transaction_ids))
            .order_by(AnomalyFlag.transaction_id.asc())
            .all()
            if transaction_ids
            else []
        )

    portfolio_data = [serialize_portfolio_snapshot(snapshot) for snapshot in portfolio]
    if not portfolio_data:
        portfolio_data = build_portfolio_growth(members, loans, transactions)

    return {
        "portfolioData": portfolio_data,
        "loanDistribution": build_loan_distribution(loans),
        "members": [serialize_member(member) for member in members],
        "loans": [serialize_loan(loan) for loan in loans],
        "transactions": [serialize_transaction(transaction) for transaction in transactions],
        "memberProfiles": {
            profile.member_id: serialize_member_profile(profile)
            for profile in profiles
        },
        "anomalyFlags": serialize_anomaly_flags(flags),
    }


@router.get("/health")
def health_check():
    database = "sqlite" if DATABASE_URL.startswith("sqlite") else "external"
    return {"status": "ok", "database": database}


@router.get("/sacco-data")
def get_sacco_data(user=Depends(require_user), db: Session = Depends(get_db)):
    return _load_sacco_data(db, user)


@router.get("/portfolio")
def get_portfolio(user=Depends(require_user), db: Session = Depends(get_db)):
    if is_admin(user):
        snapshots = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.id.asc()).all()
        portfolio_data = [serialize_portfolio_snapshot(snapshot) for snapshot in snapshots]
        if portfolio_data:
            return portfolio_data
        members = db.query(Member).order_by(Member.id.asc()).all()
        loans = db.query(Loan).order_by(Loan.issued.desc(), Loan.id.desc()).all()
        transactions = db.query(Transaction).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        return build_portfolio_growth(members, loans, transactions)

    member = member_for_user(db, user)
    loans = db.query(Loan).filter(Loan.member_id == member.id).order_by(Loan.issued.desc(), Loan.id.desc()).all()
    transactions = (
        db.query(Transaction)
        .filter(Transaction.member_id == member.id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .all()
    )
    return build_portfolio_growth([member], loans, transactions)


@router.get("/member-profiles")
def get_member_profiles(user=Depends(require_user), db: Session = Depends(get_db)):
    if is_admin(user):
        profiles = db.query(MemberProfile).order_by(MemberProfile.member_id.asc()).all()
    else:
        member = member_for_user(db, user)
        profiles = db.query(MemberProfile).filter(MemberProfile.member_id == member.id).all()

    return {
        profile.member_id: serialize_member_profile(profile)
        for profile in profiles
    }


@router.get("/anomaly-flags")
def get_anomaly_flags(user=Depends(require_user), db: Session = Depends(get_db)):
    sync_anomaly_flags(db)
    if is_admin(user):
        flags = db.query(AnomalyFlag).order_by(AnomalyFlag.transaction_id.asc()).all()
    else:
        member = member_for_user(db, user)
        transaction_ids = [row[0] for row in db.query(Transaction.id).filter(Transaction.member_id == member.id).all()]
        flags = (
            db.query(AnomalyFlag)
            .filter(AnomalyFlag.transaction_id.in_(transaction_ids))
            .order_by(AnomalyFlag.transaction_id.asc())
            .all()
            if transaction_ids
            else []
        )
    return serialize_anomaly_flags(flags)
