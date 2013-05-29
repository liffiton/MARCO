class MarcoPolo:
    def __init__(self, csolver, msolver):
        self.subs = csolver
        self.map = msolver

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
                print "Size: %d" % len(MUS)
                self.map.block_up(set(MUS))
                self.map.block_down(set(MUS))
                self.map.block_size(len(MUS))

#    def enumerate_multi(self):
#        from Queue import Queue
        #self.q = Queue()
        #csolver.register_queue(self.q)
        #csolver.register_map_check(msolver.check_seed)
        #csolver.register_map_check(lambda x: True)
#        while not self.q.empty() or self.map.has_seed():
#            seed = None
#            while not self.q.empty():
#                tmp = self.q.get()[1]
#                print "Hmmm..."
#                if self.map.check_seed(tmp):
#                    print "YAY"
#                    seed = tmp
#                    break
#            if seed is None and self.map.has_seed():
#                seed = self.map.get_seed()
#            if seed is None:
#                break
