from datetime import date
from dateutil.relativedelta import relativedelta
import calendar


class AutoDigest:
    """
    Monthly users' karma digest. Intended to monthly karma overview.
    """
    def __init__(self, day, channel, func):
        # Auto clamp day value
        self._day = max(1, min(day, 31))
        self._target_date = self._next_date(fired=False)

        self._channel = channel
        self._func = func

    def digest(self):
        # TODO: make optimizations
        if date.today() == self._target_date.date():
            self._func(self._channel)
            self._target_date = self._next_date(fired=True)

    def _next_date(self, fired):
        now = date.today()
        _, max_day = calendar.monthrange(now.year, now.month)
        day = max(1, min(self._day, max_day))

        target = date(now.year, now.month, day)
        if target >= now and not fired:
            return target
        return target + relativedelta(months=1)
