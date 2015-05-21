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
        self._timer_categories = set()  # track which timers are currently running

    # Usage:
    #  s = Statistics()
    #  with s.time("one")
    #    # do first thing
    #  with s.time("two")
    #    # do second thing
    def time(self, category):
        return self.Timer(self, category)

    # Context manager class for time() method
    class Timer:
        def __init__(self, stats, category):
            self._stats = stats
            self._category = category

        def __enter__(self):
            self._stats.start_time(self._category)

        def __exit__(self, ex_type, ex_value, traceback):
            self._stats.end_time(self._category)
            return False  # doesn't handle any exceptions itself

    def start_time(self, category):
        self._counts[category] += 1
        self._timer_categories.add(category)
        self._curr = _get_time()

    def end_time(self, category):
        self._times[category] += _get_time() - self._curr
        self._timer_categories.remove(category)

    def current_time(self):
        return _get_time() - self._start

    def get_times(self):
        self._times['total'] = self.current_time()
        for category in self._timer_categories:
            # If any timers are currently running,
            # give them the time up to this point.
            self._end_time(category)

        return self._times

    def get_counts(self):
        return self._counts

    def add_stat(self, name, value):
        self._stats[name].append(value)

    def get_stats(self):
        return self._stats
