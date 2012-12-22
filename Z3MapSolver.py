from z3.z3 import *

class Z3MapSolver:
    def __init__(self, n):
        self.solver = Solver()
        self.n = n

    def has_seed(self):
        return self.solver.check() == sat

    def get_seed(self):
        seed = set(range(self.n))  # default to all True for "high bias"
        model = self.solver.model()
        for x in model:
            if is_false(model[x]):
                seed.remove(int(x.name()))
        return seed
        
    def complement(self, aset):
        return set(range(self.n)) - aset

    def block_down(self, frompoint):
        comp = self.complement(frompoint)
        if comp:
            self.solver.add( Or( [Bool(str(i)) for i in comp] ) )
        else:
            # *could* be empty (if instance is SAT)
            self.solver.add(False)

    def block_up(self, frompoint):
        if frompoint:
            self.solver.add( Or( [Not(Bool(str(i))) for i in frompoint] ) )
        else:
            # *could* be empty (if instance is SAT)
            self.solver.add(False)

