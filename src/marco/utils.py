"""Utility class(es) for marco_py"""
from collections import Counter, defaultdict
import os
import subprocess
import threading
import types

# Three options for measuring time: choose one.
# TODO: Consider using time.process_time() (only in 3.3, though)

import time
_get_time = time.time   # wall-time

# time.clock() is not portable - behaves differently per OS
#_get_time = time.clock   # user-time

#import os
#_get_time = lambda: sum(os.times()[:4])  # combined user/sys time for this process and its children


def synchronize_class(sync_class):
    """Make any class [somewhat] thread-safe by acquiring an
    object-wide lock on every method call.  Note: this will
    *not* protect access to non-method attributes.

    Based on: http://theorangeduck.com/page/synchronized-python
    """
    lock = threading.RLock()

    def decorator(func):
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper

    orig_init = sync_class.__init__

    def __init__(self, *args, **kwargs):
        self.__lock__ = lock          # not used by this code, but could be useful
        self.__synchronized__ = True  # a flag to check in assertions
        orig_init(self, *args, **kwargs)

    sync_class.__init__ = __init__

    for key in dir(sync_class):
        val = getattr(sync_class, key)
        # synchronize all methods except __init__ and __new__ (no other thread
        # can have a reference to an object before __init__ complete,
        # as far as I know)
        if isinstance(val, (types.MethodType, types.FunctionType)) and key != '__init__' and key != '__new__':
            setattr(sync_class, key, decorator(val))

    return sync_class


class ExecutableException(Exception):
    pass


def check_executable(name, exepath):
    ''' Check whether a given program (specified with name and path)
        exists and is executable on the current platform.
        Raises an ExecutableException if either condition is not met.
    '''
    if not os.path.isfile(exepath):
        raise ExecutableException("{0} binary not found at {1}".format(name, exepath))
    try:
        # a bit of a hack to check whether we can really run it
        DEVNULL = open(os.devnull, 'wb')
        p = subprocess.Popen([exepath], stdout=DEVNULL, stderr=DEVNULL)
        p.kill()
        p.wait()
    except OSError:
        raise ExecutableException("{0} binary {1} is not executable.\nIt may be compiled for a different platform.".format(name, exepath))


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

    And counters (without associated times) can be created/maintained
    with increment_counter()
    >>> s.increment_counter('countA')
    >>> s.increment_counter('countB')
    >>> s.increment_counter('countA')
    >>> s.get_counts()
    Counter({'outer': 2, 'inner': 1, 'countA': 2, 'countB': 1})

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

    def increment_counter(self, category):
        self._counts[category] += 1

    def start_time(self, category):
        assert category not in self._active_timers
        self.increment_counter(category)
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
