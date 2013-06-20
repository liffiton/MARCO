import Queue

class MarcoPolo:
    def __init__(self, csolver, msolver, timer, config):
        self.subs = csolver
        self.map = msolver
        self.seeds = SeedManager(msolver, timer, config)
        self.timer = timer
        self.config = config

    def enumerate_basic(self):
        '''Basic MUS/MCS enumeration, as a simple example.'''
        while True:
            seed = self.map.next_seed()
            if seed is None:
                return

            if self.subs.check_subset(seed):
                MSS = self.subs.grow_current()
                yield ("S", MSS)
                self.map.block_down(MSS)
            else:
                MUS = self.subs.shrink_current()
                yield ("S", MUS)
                self.map.block_up(MUS)

    def complement(self, aset):
        return set(range(self.map.n)) - aset

    def enumerate(self):
        '''MUS/MCS enumeration with all the bells and whistles...'''
        for seed, seed_is_sat, known_max in self.seeds:
            #print seed, seed_is_sat, known_max
            
            with self.timer.measure('check'):
                if seed_is_sat is None:
                    # subset check may improve upon seed w/ unsat_core or sat_subset
                    seed_is_sat, seed = self.subs.check_subset(seed, improve_seed=True)
            
            #print seed, seed_is_sat, known_max

            if seed_is_sat:
                #print "Growing..."
                if known_max and self.config['bias'] == 'high':
                    # seed guaranteed to be maximal
                    MSS = set(seed)
                else:
                    with self.timer.measure('grow'):
                        MSS = self.subs.grow(seed)

                yield ("S", MSS)
                self.map.block_down(MSS)

                # length check to avoid checking single-clause MCSes (common), whose parent is known-UNSAT
                if self.config['mssguided'] and len(MSS) < self.map.n-1:
                    with self.timer.measure('mssguided'):
                        # add first unexplored superset to the queue
                        for i in self.complement(MSS):
                            #print "Trying", MSS | set([i])
                            if self.map.check_seed(MSS | set([i])):
                                #print "Added!"
                                self.seeds.add_seed(MSS | set([i]), False)
                                break
            
            else:
                #print "Shrinking..."
                if known_max and self.config['bias'] == 'low':
                    # seed guaranteed to be minimal
                    MUS = set(seed)
                else:
                    MUS = self.subs.shrink(seed)

                yield ("U", MUS)
                self.map.block_up(MUS)
                if self.config['smus']:
                    self.map.block_down(set(MUS))
                    self.map.block_above_size(len(MUS)-1)

class SeedManager:
    def __init__(self, msolver, timer, config):
        self.map = msolver
        self.timer = timer
        self.config = config
        self.queue = Queue.Queue()

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

        #print "Seed:", ret
        #print "Seed length:", len(ret[0])
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

