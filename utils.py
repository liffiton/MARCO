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


class Statistics:
    def __init__(self):
        self._start = _get_time()
        self._times = Counter()
        self._counts = Counter()
        self._stats = defaultdict(list)
        self._category = None

    # Usage:
    #  s = Statistics()
    #  with s.time("one")
    #    # do first thing
    #  with s.time("two")
    #    # do second thing
    def time(self, category):
        self._category = category
        return self.Timer(self)

    # Context manager class for time() method
    class Timer:
        def __init__(self, stats):
            self._stats = stats

        def __enter__(self):
            self._stats.start_time()

        def __exit__(self, ex_type, ex_value, traceback):
            self._stats.end_time()
            return False  # doesn't handle any exceptions itself

    def start_time(self):
        self._counts[self._category] += 1
        self._curr = _get_time()

    def end_time(self):
        self._times[self._category] += _get_time() - self._curr
        self._category = None

    def current_time(self):
        return _get_time() - self._start

    def get_times(self):
        self._times['total'] = self.current_time()
        if self._category:
            # If we're in a category currently,
            # give it the time up to this point.
            self._times[self._stats._category] += _get_time() - self._curr

        return self._times

    def get_counts(self):
        return self._counts

    def add_stat(self, name, value):
        self._stats[name].append(value)

    def get_stats(self):
        return self._stats
