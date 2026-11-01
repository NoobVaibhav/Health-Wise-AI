"""Row locks for the places where two people acting at the same moment could do harm: money, blood units, stock requests, theatre bookings.

The rule: take the lock FIRST, then read the numbers that decide the change. SQLite has no row locks, but a write takes the lock of the whole database, so a no-op
update is used; the next request waits its turn and then sees what the first one did. PostgreSQL gets a real SELECT ... FOR UPDATE."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session


def lock_row(db: Session, model, row_id: int) -> None:
    if db.get_bind().dialect.name == "sqlite":
        db.execute(update(model).where(model.id == row_id).values(id=model.id))
    else:
        db.execute(select(model.id).where(model.id == row_id).with_for_update())


def lock(db: Session, *rows) -> None:
    """Lock these rows (in the order given, so two requests cannot wait for each other) and drop what the session remembers about them, so the next read is fresh."""
    for row in rows:
        if row is not None:
            lock_row(db, type(row), row.id)
    for row in rows:
        if row is not None:
            db.expire(row)
