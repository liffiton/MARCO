try:
    import queue
except ImportError:
    import Queue as queue

class MarcoPolo:
    def __init__(self, csolver, msolver, timer, config):
        self.subs = csolver
        self.map = msolver
        self.seeds = SeedManager(msolver, timer, config)
        self.timer = timer
        self.config = config
        self.bias_high = self.config['bias'] == 'high'  # used frequently
        self.n = self.map.n  # number of constraints
        self.got_top = False # track whether we've explored the complete set (top of the lattice)

    def enumerate_basic(self):
        '''Basic MUS/MCS enumeration, as a simple example.'''
        while True:
            seed = self.map.next_seed()
            if seed is None:
                return

            if self.subs.check_subset(seed):
                MSS = self.subs.grow(seed)
                yield ("S", MSS)
                self.map.block_down(MSS)
            else:
                MUS = self.subs.shrink(seed)
                yield ("S", MUS)
                self.map.block_up(MUS)

    def enumerate(self):
        '''MUS/MCS enumeration with all the bells and whistles...'''
        for seed, seed_is_sat, known_max in self.seeds:
            
            with self.timer.measure('check'):
                # subset check may improve upon seed w/ unsat_core or sat_subset
                seed_is_sat, seed = self.subs.check_subset(seed, improve_seed=True)

            if seed_is_sat:
                if self.bias_high and known_max:
                    MSS = seed
                else:
                    with self.timer.measure('grow'):
                        MSS = self.subs.grow(seed, inplace=True)

                yield ("S", MSS)
                self.map.block_down(MSS)

            else:
                self.got_top = True  # any unsat set covers the top of the lattice
                if known_max and not self.bias_high:
                    MUS = seed
                else:
                    with self.timer.measure('shrink'):
                        MUS = self.subs.shrink(seed)

                yield ("U", MUS)
                self.map.block_up(MUS)


class SeedManager:
    def __init__(self, msolver, timer, config):
        self.map = msolver
        self.timer = timer
        self.config = config
        self.queue = queue.Queue()

    def __iter__(self):
        return self

    def __next__(self):
        with self.timer.measure('seed'):
            # fields of ret: ( seedvalues, is_sat (T=SAT / F=UNSAT / None=unknown), known_max (T/F) )
            if not self.queue.empty():
                ret = self.queue.get()
            else:
                seed, known_max = self.seed_from_solver()
                if seed is None:
                    raise StopIteration
                ret = (seed, None, known_max)

        return ret

    def add_seed(self, seed, is_sat):
        self.queue.put( (seed, is_sat, False) )

    def seed_from_solver(self):
        if self.config['maxseed']:
            return self.map.next_max_seed(), True
        else:
            return self.map.next_seed(), False

    # for python 2 compatibility
    next = __next__

