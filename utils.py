"""Utility class(es) for marco_py"""

# time.clock() is not portable - behaves differently per OS
# TODO: Consider using time.process_time() (only in 3.3, though)
#from time import clock
from os import times
from collections import Counter

class Timer:
    def __init__(self):
        self.curr = 0
        self.times = Counter()
        self.category = None

    def total_time(self):
        """Sum times[0-3]: user&sys for proc&children."""
        return sum(times()[:4])

    def measure(self, category):
        self.category = category
        return self

    def __enter__(self):
        self.curr = self.total_time()

    def __exit__(self, ex_type, ex_value, traceback):
        self.times[self.category] += self.total_time() - self.curr
        return False  # doesn't handle any exceptions itself
    
    def get_times(self):
        self.times['_total'] = self.total_time()
        return self.times

