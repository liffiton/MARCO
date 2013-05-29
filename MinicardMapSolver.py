from pyminisolvers import minicard

class MinicardMapSolver:
    def __init__(self, n):
        self.n = n
        self.k = n  # initial lower bound on # of True variables
        self.solver = minicard.Solver()
        while self.solver.nvars() < self.n:
            self.solver.new_var(True)  # bias to True

        # add "bound-setting" variables
        while self.solver.nvars() < self.n*2:
            self.solver.new_var()

        # add cardinality constraint
        # want: generic AtLeastK over all n variables
        # how: make AtLeast([n vars, n bound-setting vars], n)
        #      then, assume the desired k out of the n bound-setting vars.
        # e.g.: for real vars a,b,c: AtLeast([a,b,c, x,y,z], 3)
        #       for AtLeast 3: assume(-x,-y,-z)
        #       for AtLeast 1: assume(-x)
        # and to make AtLeast into an AtMost:
        #   AtLeast([lits], k) ==> AtMost([-lits], #lits-k)
        self.solver.add_atmost([-(x+1) for x in range(self.n * 2)], self.n)

    def solve_with_bound(self, k):
        return self.solver.solve([-(x+1+self.n) for x in range(k)] + [(x+1)+self.n+k for x in range(self.n-k)])

    def has_seed(self):
        '''
            Find the next-most-maximal model.
        '''
        while self.k >= 0 and not self.solve_with_bound(self.k):
            self.k -= 1
            if not self.solve_with_bound(0):
                # no more models
                self.k = -1
                break

        if self.k < 0:
            return False
        else:
            return True

    def get_seed(self):
        model = self.solver.get_model()
        seed = [i for i in range(self.n) if model[i]]
        # slower:
        #seed = set()
        #for i in range(self.n):
        #    if self.solver.model_value(i+1):
        #        seed.add(i)
        return seed

    def check_seed(self, seed):
        raise NotImplementedError  # TODO: how to check seeds when our instance has the cardinality constraint in it...?
        
        return self.solver.solve(seed)

    def complement(self, aset):
        return set(range(self.n)) - aset

    def block_down(self, frompoint):
        comp = self.complement(frompoint)
        if comp:
            self.solver.add_clause([i+1 for i in comp])
        else:
            # *could* be empty (if instance is SAT)
            self.solver.add_clause( [] )

    def block_up(self, frompoint):
        if frompoint:
            self.solver.add_clause([-(i+1) for i in frompoint])
        else:
            # *could* be empty (if instance is SAT)
            self.solver.add_clause( [] )

    def block_size(self, size):
        self.solver.add_atmost([(x+1) for x in range(self.n)], size-1)
        self.k = size-1
        print "Set: %d" % self.k
