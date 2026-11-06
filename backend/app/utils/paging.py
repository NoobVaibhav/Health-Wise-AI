"""Paging for the long lists. The answer stays a plain list; the size of the whole list is in the X-Total-Count header, so a screen can offer 'show more'."""
from fastapi import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_PAGE = 100


def total_header(response: Response, total: int) -> None:
    response.headers["X-Total-Count"] = str(total)


def page_of_list(response: Response, rows: list, limit: int, offset: int) -> list:
    """For lists that are filtered or sorted in Python: the slice asked for, and the full count in the header."""
    total_header(response, len(rows))
    return rows[offset:offset + limit]


def page_of_query(db: Session, response: Response, query, limit: int, offset: int):
    """For a SELECT that the database can count and cut: only the rows of the page are read."""
    total_header(response, db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    return db.scalars(query.limit(limit).offset(offset)).all()
