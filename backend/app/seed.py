from sqlalchemy.orm import Session


def seed_database(db: Session) -> None:
    # Production data should enter through signup and admin CRUD flows.
    # Keeping this no-op prevents demo records from reappearing on restart.
    return None
