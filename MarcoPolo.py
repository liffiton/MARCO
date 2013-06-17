class MarcoPolo:
    def __init__(self, csolver, msolver, timer, config):
        self.subs = csolver
        self.map = msolver
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

    def enumerate(self):
        '''MUS/MCS enumeration with all the bells and whistles...'''
        while True:
            with self.timer.measure('seed'):
                if self.config['maxseed']:
                    seed = self.map.next_max_seed()
                else:
                    seed = self.map.next_seed()
                if seed is None:
                    return
                #print "Seed:", seed
                #print "Seed length:", len(seed)

            with self.timer.measure('check'):
                seed_is_sat = self.subs.check_subset(seed)

            if seed_is_sat:
                #print "Growing..."
                if self.config['maxseed'] and self.config['bias'] == 'high':
                    # seed guaranteed to be maximal
                    MSS = set(seed)
                else:
                    with self.timer.measure('grow'):
                        try:
                            MSS = self.subs.grow_current()
                        except NotImplementedError:
                            # not yet implemented for Z3 solver
                            MSS = self.subs.grow(seed)

                yield ("S", MSS)
                self.map.block_down(MSS)

            else:
                #print "Shrinking..."
                if self.config['maxseed'] and self.config['bias'] == 'low':
                    # seed guaranteed to be minimal
                    MUS = set(seed)
                else:
                    with self.timer.measure('shrink'):
                        MUS = self.subs.shrink_current()

                yield ("U", MUS)
                self.map.block_up(MUS)
                if self.config['smus']:
                    self.map.block_down(set(MUS))
                    self.map.block_above_size(len(MUS)-1)

