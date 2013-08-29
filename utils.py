"""Utility class(es) for marco_py"""

# time.clock() is not portable - behaves differently per OS
# TODO: Consider using time.process_time() (only in 3.3, though)
import time
import os
from collections import Counter, defaultdict

get_time = lambda: sum(os.times()[:4])  # combined user/sys time for this process and its children
get_time = time.time   # wall-time
#get_time = time.clock   # user-time


class Statistics:
    def __init__(self):
        self._start = get_time()
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
        return self

    def __enter__(self):
        self._counts[self._category] += 1
        self._curr = get_time()

    def __exit__(self, ex_type, ex_value, traceback):
        self._times[self._category] += get_time() - self._curr
        self._category = None
        return False  # doesn't handle any exceptions itself

    def get_times(self):
        self._times['total'] = get_time() - self._start
        if self._category:
            # If we're in a category currently,
            # give it the time up to this point.
            self._times[self._category] += get_time() - self._curr

        return self._times

    def get_counts(self):
        return self._counts

    def add_stat(self, name, value):
        self._stats[name].append(value)

    def get_stats(self):
        return self._stats
