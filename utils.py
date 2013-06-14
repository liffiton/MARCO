"""Utility class(es) for marco_py"""

# time.clock() is not portable - behaves differently per OS
# TODO: Consider using time.process_time() (only in 3.3, though)
import time
import os
from collections import Counter

def get_time():
    #return sum(os.times()[:4])  # combined user/sys time for this process and its children
    return time.time()   # wall-time
    #return time.clock()   # user-time

class Timer:
    def __init__(self):
        self.start = get_time()
        self.times = Counter()
        self.category = None

    def measure(self, category):
        self.category = category
        return self

    def __enter__(self):
        self.curr = get_time()

    def __exit__(self, ex_type, ex_value, traceback):
        self.times[self.category] += get_time() - self.curr
        self.category = None
        return False  # doesn't handle any exceptions itself
    
    def get_times(self):
        self.times['total'] = get_time() - self.start
        if self.category:
            # If we're in a category currently,
            # give it the time up to this point.
            self.times[self.category] += get_time() - self.curr

        return self.times

