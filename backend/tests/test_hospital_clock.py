"""'Today' means today at the hospital (India), not on the server. A server in UTC is still on yesterday's date for the first five and a half hours of every Indian day,
which used to refuse a baby born this morning, and treat stock that expires today as already expired. The clock is frozen, so these do not depend on the real date."""
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import BaseModel

import app.utils.validators as v
from app.utils import clock

UTC_EVENING = datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc)        # 01:30 on 6 November at the hospital


class Dob(BaseModel):
    d: v.DateOfBirth = None


class Past(BaseModel):
    d: v.PastOrTodayDate = None


class Planned(BaseModel):
    d: v.PlannedDate = None


@pytest.fixture()
def frozen(monkeypatch):
    monkeypatch.setattr(clock, "_utc_now", lambda: UTC_EVENING)


def test_hospital_today_is_ahead_of_a_utc_server_in_the_morning(frozen):
    assert clock.hospital_today() == date(2026, 11, 6) and UTC_EVENING.date() == date(2026, 11, 5)
    assert clock.hospital_now() == datetime(2026, 11, 6, 1, 30)


def test_a_baby_born_today_at_the_hospital_is_accepted_and_tomorrow_is_not(frozen):
    assert Dob(d=date(2026, 11, 6)).d == date(2026, 11, 6)
    with pytest.raises(ValueError):
        Dob(d=date(2026, 11, 7))


def test_dates_that_may_be_today_but_not_later(frozen):
    assert Past(d=date(2026, 11, 6)).d
    with pytest.raises(ValueError):
        Past(d=date(2026, 11, 7))


def test_planned_dates_count_two_years_from_the_hospital_day(frozen):
    assert Planned(d=date(2026, 11, 6) + timedelta(days=731)).d
    with pytest.raises(ValueError):
        Planned(d=date(2026, 11, 6) + timedelta(days=732))


def test_recorded_times_use_the_hospital_wall_clock(frozen):
    class T(BaseModel):
        t: v.RecordedTime
    assert T(t=datetime(2026, 11, 6, 1, 20)).t
    with pytest.raises(ValueError):
        T(t=datetime(2026, 11, 6, 3, 0))                 # more than the one hour of grace ahead of 01:30


def test_the_age_limit_counts_from_the_hospital_day(frozen):
    assert Dob(d=date(1906, 11, 6)).d                      # 120 today
    with pytest.raises(ValueError):
        Dob(d=date(1905, 11, 5))                           # 121


def test_stock_that_expires_today_is_sellable_and_yesterdays_is_not(frozen):
    from app.services.stock_service import is_usable as sellable
    class Row:
        quantity, recalled = 5, False
        def __init__(self, expiry): self.expiry_date = expiry
    assert sellable(Row(date(2026, 11, 6))) and not sellable(Row(date(2026, 11, 5)))
