from math import ceil
from typing import Callable

from fastapi import Query
from sqlalchemy.orm import Query as SqlAlchemyQuery


def page_query(default: int | None = None) -> int | None:
    return Query(default, ge=1)


def per_page_query(default: int | None = None) -> int | None:
    return Query(default, ge=1, le=100)


def paginate(query: SqlAlchemyQuery, page: int, per_page: int, serializer: Callable) -> dict:
    total = query.order_by(None).count()
    rows = query.limit(per_page).offset((page - 1) * per_page).all()
    total_pages = max(1, ceil(total / per_page)) if total else 1

    return {
        "items": [serializer(row) for row in rows],
        "meta": {
            "page": page,
            "perPage": per_page,
            "total": total,
            "totalPages": total_pages,
            "hasNext": page < total_pages,
            "hasPrevious": page > 1,
        },
    }
