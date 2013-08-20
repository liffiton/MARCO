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
        self.singleton_MCSes = set()  # store singleton MCSes to pass as hard clauses to shrink()

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
                yield ("U", MUS)
                self.map.block_up(MUS)

    def enumerate(self):
        '''MUS/MCS enumeration with all the bells and whistles...'''
        for seed in self.seeds:

            if self.config['maxseed'] == 'always':
                with self.timer.measure('maximize'):
                    seed = self.map.maximize_seed(seed, direction=self.bias_high)
            
            with self.timer.measure('check'):
                # subset check may improve upon seed w/ unsat_core or sat_subset
                seed_is_sat, seed = self.subs.check_subset(seed, improve_seed=True)

            # --half-max: Only maximize if we're UNSAT w/ a low bias or SAT w/ a high bias
            if self.config['maxseed'] == 'half' and (seed_is_sat == self.bias_high):
                # Maximize within Map and re-check satisfiability
                with self.timer.measure('maximize'):
                    seed = self.map.maximize_seed(seed, direction=self.bias_high)
                with self.timer.measure('check'):
                    # improve_seed set to True in case maximized seed needs to go in opposite
                    # direction of the maximization (i.e., UNSAT seed w/ high bias, SAT w/ low bias)
                    # (otherwise, no improvement is possible as we maximized it already)
                    seed_is_sat, seed = self.subs.check_subset(seed, improve_seed=True)

            if seed_is_sat:
                if self.bias_high and (self.config['nogrow'] or self.config['maxseed']):
                    MSS = seed
                else:
                    with self.timer.measure('grow'):
                        MSS = self.subs.grow(seed, inplace=True)

                yield ("S", MSS)
                self.map.block_down(MSS)

                if self.config['use_singletons']:
                    if len(MSS) == self.n-1:
                        # singleton MCS, record to pass as hard clause to shrink()
                        singleton = self.subs.complement(MSS).pop()  # TODO: more efficient...
                        self.singleton_MCSes.add(singleton)

                if self.config['mssguided']:
                    with self.timer.measure('mssguided'):
                        # don't check parents if parent is top and we've already seen it (common)
                        if len(MSS) < self.n-1 or not self.got_top:
                            # add any unexplored superset to the queue
                            newseed = self.map.find_above(MSS)
                            if newseed:
                                self.seeds.add_seed(newseed)

            else:
                self.got_top = True  # any unsat set covers the top of the lattice
                if self.config['maxseed'] and not self.bias_high:
                    MUS = seed
                else:
                    with self.timer.measure('shrink'):
                        MUS = self.subs.shrink(seed, hard=self.singleton_MCSes)

                yield ("U", MUS)
                self.map.block_up(MUS)
                if self.config['smus']:
                    self.map.block_down(MUS)
                    self.map.block_above_size(len(MUS)-1)


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
            if not self.queue.empty():
                return self.queue.get()
            else:
                seed = self.seed_from_solver()
                if seed is None:
                    raise StopIteration
                return seed

    def add_seed(self, seed):
        self.queue.put(seed)

    def seed_from_solver(self):
        return self.map.next_seed()

    # for python 2 compatibility
    next = __next__
