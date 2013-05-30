from MinisatMapSolver import MinisatMapSolver

class MarcoPolo:
    def __init__(self, csolver, msolver=None):
        self.subs = csolver
        if msolver is None:
            self.map = MinisatMapSolver(csolver.n)
        else:
            self.map = msolver

    def enumerate(self):
        while self.map.has_seed():
            seed = self.map.get_seed()
            #print "Seed:", seed
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
                self.map.block_up(MUS)

