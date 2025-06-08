import os
import queue
import threading


class MarcoPolo(object):
    def __init__(self, csolver, msolver, stats, config, pipe=None):
        self.subs = csolver
        self.map = msolver
        self.seeds = SeedManager(msolver, stats, config)
        self.stats = stats
        self.config = config
        self.bias_high = self.config['bias'] == 'MUSes'  # used frequently
        self.n = self.map.n   # number of constraints
        self.got_top = False  # track whether we've explored the complete set (top of the lattice)

        self.pipe = pipe
        # if a pipe is provided, use it to receive results from other enumerators
        if self.pipe:
            self.recv_thread = threading.Thread(target=self.receive_thread)
            self.recv_thread.start()

    def receive_thread(self):
        while self.pipe.poll(None):
            with self.stats.time('receive'):
                res = self.pipe.recv()
                if res == 'terminate':
                    # exit process on terminate message
                    os._exit(0)
                # Otherwise, we've received another result,
                # update blocking clauses.
                # Requires map solver to be thread-safe:
                assert hasattr(self.map, "__synchronized__") and self.map.__synchronized__

                if self.config['comms_ignore']:
                    continue

                if res[0] == 'S':
                    self.map.block_down(res[1])
                elif res[0] == 'U':
                    self.map.block_up(res[1])
                else:
                    assert False

    def record_delta(self, name, oldlen, newlen, up):
        if up:
            assert newlen >= oldlen
            self.stats.add_stat("delta.%s.up" % name, float(newlen - oldlen) / self.n)
        else:
            assert newlen <= oldlen
            self.stats.add_stat("delta.%s.down" % name, float(oldlen - newlen) / self.n)

    def enumerate(self):
        '''MUS/MCS enumeration with all the bells and whistles...'''

        for seed, known_max in self.seeds:

            if self.config['verbose']:
                print("- Initial seed: %s" % " ".join([str(x) for x in seed]))

            with self.stats.time('check'):
                # subset check may improve upon seed w/ unsat_core or sat_subset
                oldlen = len(seed)
                seed_is_sat, seed = self.subs.check_subset(seed, improve_seed=True)
                self.record_delta('checkA', oldlen, len(seed), seed_is_sat)
                known_max = (known_max and (seed_is_sat == self.bias_high))

            if self.config['verbose']:
                print("- Seed is %s." % {True: "SAT", False: "UNSAT"}[seed_is_sat])
                if known_max:
                    print("- Seed is known to be optimal.")
                else:
                    print("- Seed improved by check: %s" % " ".join([str(x) for x in seed]))

            if seed_is_sat:
                if known_max:
                    MSS = seed
                else:
                    with self.stats.time('grow'):
                        oldlen = len(seed)
                        MSS = self.subs.grow(seed)
                        self.record_delta('grow', oldlen, len(MSS), True)

                    if self.config['verbose']:
                        print("- Grow() -> MSS")

                with self.stats.time('block'):
                    res = ("S", MSS)
                    yield res

                    try:
                        self.subs.increment_MSS()
                    except AttributeError:
                        pass

                    self.map.block_down(MSS)

                if self.config['verbose']:
                    print("- MSS blocked.")

            else:  # seed is not SAT
                self.got_top = True  # any unsat set covers the top of the lattice
                if known_max:
                    MUS = seed
                else:
                    with self.stats.time('shrink'):
                        oldlen = len(seed)

                        MUS = self.subs.shrink(seed)

                        if MUS is None:
                            # seed was explored in another process
                            # in the meantime
                            self.stats.increment_counter("parallel_rejected")
                            continue

                        self.record_delta('shrink', oldlen, len(MUS), False)

                    if self.config['verbose']:
                        print("- Shrink() -> MUS")

                with self.stats.time('block'):
                    res = ("U", MUS)
                    yield res

                    try:
                        self.subs.increment_MUS()
                    except AttributeError:
                        pass

                    self.map.block_up(MUS)

                if self.config['verbose']:
                    print("- MUS blocked.")

        if self.pipe:
            self.pipe.send(('complete', self.stats))
            self.recv_thread.join()


class SeedManager(object):
    def __init__(self, msolver, stats, config):
        self.map = msolver
        self.stats = stats
        self.config = config
        self._seed_queue = queue.Queue()

    def __iter__(self):
        return self

    def __next__(self):
        with self.stats.time('seed'):
            if not self._seed_queue.empty():
                return self._seed_queue.get()
            else:
                seed, known_max = self.seed_from_solver()
                if seed is None:
                    raise StopIteration
                return seed, known_max

    def add_seed(self, seed, known_max):
        self._seed_queue.put((seed, known_max))

    def seed_from_solver(self):
        known_max = self.config['maximize']
        return self.map.next_seed(), known_max
