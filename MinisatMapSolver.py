from pyminisolvers import minisat

class MinisatMapSolver:
    def __init__(self, n):
        self.n = n
        self.solver = minisat.Solver()
        while self.solver.nvars() < self.n:
            self.solver.new_var(True)  # bias to True

    def has_seed(self):
        return self.solver.solve()

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

