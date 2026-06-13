import os

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import BACKEND_DIR

DEFAULT_SQLITE_PATH = BACKEND_DIR / "umojafunds.sqlite3"


def _legacy_mysql_url() -> str | None:
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME")

    if not all([user, password, host, name]) or password == "YOUR_PASSWORD":
        return None

    return f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{name}"


DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or _legacy_mysql_url()
    or f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_options = {
    "connect_args": connect_args,
    "pool_pre_ping": not DATABASE_URL.startswith("sqlite"),
}

if not DATABASE_URL.startswith("sqlite"):
    engine_options.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        }
    )

engine = create_engine(DATABASE_URL, **engine_options)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import models  # noqa: F401
    from app.models import security  # noqa: F401
    from app.seed import seed_database

    Base.metadata.create_all(bind=engine)
    _sync_lightweight_schema()

    db = SessionLocal()
    try:
        _link_members_to_users(db)
        seed_database(db)
    finally:
        db.close()


def _sync_lightweight_schema() -> None:
    """Apply small additive schema changes for local deployments without migrations."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as connection:
        def columns(table: str) -> set[str]:
            return {column["name"] for column in inspector.get_columns(table)}

        def add_column(table: str, column: str, sqlite_type: str, mysql_type: str | None = None) -> None:
            column_type = sqlite_type if DATABASE_URL.startswith("sqlite") else (mysql_type or sqlite_type)
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))

        def ensure_index(table: str, index_name: str, column_sql: str, unique: bool = False) -> None:
            existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
            if index_name in existing_indexes:
                return
            unique_sql = "UNIQUE " if unique else ""
            connection.execute(text(f"CREATE {unique_sql}INDEX {index_name} ON {table}({column_sql})"))

        if "members" in table_names:
            member_columns = columns("members")
            if "user_id" not in member_columns:
                add_column("members", "user_id", "INTEGER")

        if "auth_tokens" in table_names:
            token_columns = columns("auth_tokens")
            if "last_seen_at" not in token_columns:
                if DATABASE_URL.startswith("sqlite"):
                    connection.execute(text("ALTER TABLE auth_tokens ADD COLUMN last_seen_at DATETIME"))
                    connection.execute(text("UPDATE auth_tokens SET last_seen_at = created_at WHERE last_seen_at IS NULL"))
                else:
                    connection.execute(text("ALTER TABLE auth_tokens ADD COLUMN last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"))

        if "membership_applications" in table_names:
            application_columns = columns("membership_applications")
            for column, column_type in {
                "phone": "VARCHAR(50) NOT NULL DEFAULT ''",
                "national_id": "VARCHAR(100) NOT NULL DEFAULT ''",
                "address": "VARCHAR(255) NOT NULL DEFAULT ''",
                "notes": "VARCHAR(500) NOT NULL DEFAULT ''",
                "reviewed_at": "DATETIME",
                "reviewed_by": "INTEGER",
                "member_id": "VARCHAR(20)",
            }.items():
                if column not in application_columns:
                    add_column("membership_applications", column, column_type)

        if "loan_applications" in table_names:
            loan_application_columns = columns("loan_applications")
            for column, column_type in {
                "purpose": "VARCHAR(500) NOT NULL DEFAULT ''",
                "term_months": "INTEGER NOT NULL DEFAULT 12",
                "reviewed_at": "DATETIME",
                "reviewed_by": "INTEGER",
                "loan_id": "VARCHAR(30)",
            }.items():
                if column not in loan_application_columns:
                    add_column("loan_applications", column, column_type)

        if "transaction_requests" in table_names:
            transaction_request_columns = columns("transaction_requests")
            if "loan_id" not in transaction_request_columns:
                add_column("transaction_requests", "loan_id", "VARCHAR(30)")
            for column, column_type in {
                "mpesa_receipt_number": "VARCHAR(100) NOT NULL DEFAULT ''",
                "mpesa_phone_number": "VARCHAR(30) NOT NULL DEFAULT ''",
                "mpesa_checkout_request_id": "VARCHAR(100) NOT NULL DEFAULT ''",
                "mpesa_merchant_request_id": "VARCHAR(100) NOT NULL DEFAULT ''",
                "mpesa_result_code": "VARCHAR(20) NOT NULL DEFAULT ''",
                "mpesa_result_description": "VARCHAR(255) NOT NULL DEFAULT ''",
                "mpesa_raw_payload": "TEXT",
            }.items():
                if column not in transaction_request_columns:
                    add_column("transaction_requests", column, column_type)

        if "transactions" in table_names:
            transaction_columns = columns("transactions")
            for column, column_type in {
                "mpesa_receipt_number": "VARCHAR(100) NOT NULL DEFAULT ''",
                "mpesa_phone_number": "VARCHAR(30) NOT NULL DEFAULT ''",
                "mpesa_checkout_request_id": "VARCHAR(100) NOT NULL DEFAULT ''",
                "mpesa_merchant_request_id": "VARCHAR(100) NOT NULL DEFAULT ''",
                "mpesa_result_code": "VARCHAR(20) NOT NULL DEFAULT ''",
                "mpesa_result_description": "VARCHAR(255) NOT NULL DEFAULT ''",
                "mpesa_raw_payload": "TEXT",
            }.items():
                if column not in transaction_columns:
                    add_column("transactions", column, column_type)

        if "product_analytics_events" in table_names:
            event_columns = columns("product_analytics_events")
            for column, column_type in {
                "path": "VARCHAR(255) DEFAULT ''",
                "duration_seconds": "INTEGER",
                "properties_json": "TEXT",
                "occurred_at": "DATETIME",
                "created_at": "DATETIME",
            }.items():
                if column not in event_columns:
                    add_column("product_analytics_events", column, column_type)
            if "properties_json" not in event_columns:
                connection.execute(text("UPDATE product_analytics_events SET properties_json = '{}' WHERE properties_json IS NULL OR properties_json = ''"))
            if "occurred_at" not in event_columns:
                connection.execute(text("UPDATE product_analytics_events SET occurred_at = created_at WHERE occurred_at IS NULL AND created_at IS NOT NULL"))
                connection.execute(text("UPDATE product_analytics_events SET occurred_at = CURRENT_TIMESTAMP WHERE occurred_at IS NULL"))
            if "created_at" not in event_columns:
                connection.execute(text("UPDATE product_analytics_events SET created_at = occurred_at WHERE created_at IS NULL AND occurred_at IS NOT NULL"))
                connection.execute(text("UPDATE product_analytics_events SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))

        if "security_events" in table_names:
            security_event_columns = columns("security_events")
            for column, column_type in {
                "user_id": "INTEGER",
                "user_agent": "VARCHAR(255) NOT NULL DEFAULT ''",
                "method": "VARCHAR(10) NOT NULL DEFAULT ''",
                "path": "VARCHAR(255) NOT NULL DEFAULT ''",
                "status_code": "INTEGER",
            }.items():
                if column not in security_event_columns:
                    add_column("security_events", column, column_type)

        for table in table_names:
            if table == "members" and "user_id" in columns(table) and DATABASE_URL.startswith("sqlite"):
                existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
                if "ix_members_user_id" not in existing_indexes:
                    connection.execute(text("CREATE UNIQUE INDEX ix_members_user_id ON members(user_id) WHERE user_id IS NOT NULL"))

        if "loans" in table_names:
            ensure_index("loans", "ix_loans_member_issued_id", "member_id, issued, id")
            ensure_index("loans", "ix_loans_status_due", "status, due")
        if "transactions" in table_names:
            ensure_index("transactions", "ix_transactions_member_date_id", "member_id, date, id")
            ensure_index("transactions", "ix_transactions_type_date", "type, date")
            ensure_index("transactions", "ix_transactions_mpesa_receipt_number", "mpesa_receipt_number")
        if "transaction_requests" in table_names:
            ensure_index("transaction_requests", "ix_transaction_requests_mpesa_receipt_number", "mpesa_receipt_number")
            ensure_index("transaction_requests", "ix_transaction_requests_mpesa_checkout_request_id", "mpesa_checkout_request_id")
        if "loan_applications" in table_names:
            ensure_index("loan_applications", "ix_loan_applications_member_created_id", "member_id, created_at, id")
            ensure_index("loan_applications", "ix_loan_applications_status_created", "status, created_at")
        if "mpesa_payments" in table_names:
            ensure_index("mpesa_payments", "ix_mpesa_payments_receipt_number", "receipt_number")
            ensure_index("mpesa_payments", "ix_mpesa_payments_checkout_request_id", "checkout_request_id")
            ensure_index("mpesa_payments", "ix_mpesa_payments_bill_ref_number", "bill_ref_number")
        if "rate_limit_events" in table_names:
            ensure_index("rate_limit_events", "ix_rate_limit_events_key_created", "`key`, created_at" if not DATABASE_URL.startswith("sqlite") else "key, created_at")
        if "security_events" in table_names:
            ensure_index("security_events", "ix_security_events_severity_created", "severity, created_at")
            ensure_index("security_events", "ix_security_events_type_created", "event_type, created_at")
            ensure_index("security_events", "ix_security_events_ip_created", "ip_address, created_at")

    Base.metadata.create_all(bind=engine)


def _link_members_to_users(db) -> None:
    from app.models.models import Member, User

    members = db.query(Member).filter(Member.user_id.is_(None)).all()
    changed = False
    for member in members:
        user = db.query(User).filter(User.email == member.email).first()
        if user:
            member.user_id = user.id
            changed = True
    if changed:
        db.commit()
