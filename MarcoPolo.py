class MarcoPolo:
    def __init__(self, csolver, msolver, config):
        self.subs = csolver
        self.map = msolver
        self.config = config

    def enumerate(self):
        while self.map.has_seed():
            seed = self.map.get_seed()
            #print "Seed:", seed
            #print "Seed length:", len(seed)
            if self.subs.check_subset(seed):
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
                self.map.block_up(set(MUS))
                if (self.config['smus']):
                    self.map.block_down(set(MUS))
                    self.map.block_above_size(len(MUS)-1)

