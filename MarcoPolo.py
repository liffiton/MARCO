class MarcoPolo:
    def __init__(self, csolver, msolver, timer, config):
        self.subs = csolver
        self.map = msolver
        self.timer = timer
        self.config = config

    def enumerate(self):
        while True:
            with self.timer.measure('seed'):
                if not self.map.has_seed():
                    break
                seed = self.map.get_seed()
                #print "Seed:", seed
                #print "Seed length:", len(seed)

                seed_is_sat = self.subs.check_subset(seed)

            with self.timer.measure('subsets'):
                if seed_is_sat:
                    #print "Growing..."
                    try:
                        MSS = self.subs.grow_current()
                    except NotImplementedError:
                        # not yet implemented for Z3 solver
                        MSS = self.subs.grow(seed)
                    yield ("S", MSS)
                    self.map.block_down(MSS)
                else:
                    #print "Shrinking..."
                    MUS = self.subs.shrink_current()
                    yield ("U", MUS)
                    self.map.block_up(MUS)
                    if (self.config['smus']):
                        self.map.block_down(set(MUS))
                        self.map.block_above_size(len(MUS)-1)

