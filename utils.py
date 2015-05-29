"""Utility class(es) for marco_py"""
from collections import Counter, defaultdict

# Three options for measuring time: choose one.
# TODO: Consider using time.process_time() (only in 3.3, though)

import time
_get_time = time.time   # wall-time

# time.clock() is not portable - behaves differently per OS
#_get_time = time.clock   # user-time

#import os
#_get_time = lambda: sum(os.times()[:4])  # combined user/sys time for this process and its children


class Statistics(object):
    """
    >>> import time   # for time.sleep() in below examples
    >>> s = Statistics()

    The Statistics object provides a simple method for timing blocks of
    code with a context manager.  Timed blocks may be nested.
    >>> with s.time("outer"):
    ...     time.sleep(0.1)
    ...     with s.time("inner"):
    ...         time.sleep(0.05)
    >>> ["%s: %0.2f" % (key, value) for key, value in s.get_times().items()]
    ['total: 0.15', 'outer: 0.15', 'inner: 0.05']

    Times are accumulated across all calls to time() that share a 'category',
    and the count for each category (how many times it was measured) is
    available for simple averaging or other analysis.
    >>> with s.time("outer"):
    ...     time.sleep(0.02)
    >>> ["%s: %0.2f" % (key, value) for key, value in s.get_times().items()]
    ['total: 0.17', 'outer: 0.17', 'inner: 0.05']
    >>> s.get_counts()
    Counter({'outer': 2, 'inner': 1})

    The object also provides a method for collecting arbitrary statistics.
    Every value added for a given string is appended to a list.
    >>> s.add_stat('statA', 5)
    >>> s.add_stat('statB', 123)
    >>> s.add_stat('statA', 8)
    >>> dict(s.get_stats())
    {'statB': [123], 'statA': [5, 8]}
    """
    def __init__(self):
        self._start = _get_time()
        self._times = Counter()
        self._counts = Counter()
        self._stats = defaultdict(list)
        self._active_timers = {}   # dict: key=category, value=start time

    def time(self, category):
        return self.TimerContext(self, category)

    # Context manager class for time() method
    class TimerContext(object):
        def __init__(self, stats, category):
            self._stats = stats
            self._category = category

        def __enter__(self):
            self._stats.start_time(self._category)

        def __exit__(self, ex_type, ex_value, traceback):
            self._stats.end_time(self._category)
            return False  # doesn't handle any exceptions itself

    def start_time(self, category):
        assert category not in self._active_timers
        self._counts[category] += 1
        self._active_timers[category] = _get_time()

    def end_time(self, category):
        self.update_time(category)
        del self._active_timers[category]

    def update_time(self, category):
        now = _get_time()
        self._times[category] += now - self._active_timers[category]
        # reset the "start time" as previous time is now counted
        self._active_timers[category] = now

    def total_time(self):
        return _get_time() - self._start

    def get_times(self):
        self._times['total'] = self.total_time()
        for category in self._active_timers:
            # If any timers are currently running,
            # give them the time up to this point.
            self.update_time(category)

        return self._times

    def get_counts(self):
        return self._counts

    def add_stat(self, name, value):
        self._stats[name].append(value)

    def get_stats(self):
        return self._stats
