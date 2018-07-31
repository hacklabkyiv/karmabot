from unittest.mock import MagicMock
from datetime import date
import calendar
from karmabot.auto_digest import AutoDigest


def test_date_last():
    now = date.today()
    _, max_day = calendar.monthrange(now.year, now.month)
    a = AutoDigest(31, MagicMock(), MagicMock())
    assert a._target_date == date(now.year, now.month, max_day)

def test_today():
    a = AutoDigest(date.today().day, MagicMock(), MagicMock())
    assert a._target_date == date.today()
