import abc
from pyminisolvers import minisolvers


class MapSolver(object):
    """The abstract base class for any MapSolver, implementing common utility functions."""
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod  # must be overridden, but can be called via super()
    def __init__(self, n, bias=True, dump=None):
        """Common initialization.

        Args:
            n: The number of constraints to map.
            bias: Boolean specifying the solver's bias.  True is a
                  high/inclusion/MUS bias; False is a low/exclusion/MSS bias;
                  None is no bias.
        """
        self.n = n
        self.bias = bias
        self.all_n = set(range(1, n+1))  # used in complement fairly frequently
        self.dump = dump

    @abc.abstractmethod
    def next_seed(self):
        pass

    @abc.abstractproperty
    def solver(self):
        pass

    def set_rnd_seed(self, seed):
        """Set the underlying solver's random seed."""
        self.solver.set_rnd_seed(seed)

    def check_seed(self, seed):
        """Check whether a given seed is still unexplored.

        Returns:
            True if seed is unexplored (i.e., its corresponding assignment is a model)
        """
        return self.solver.check_complete(positive_lits=seed)

    def find_above(self, seed):
        """Look for and return any unexplored point including the given seed.
            Calling map.find_above(MSS) after map.block_down(MSS) will thus find
            strict supersets of the MSS, as the MSS itself has been blocked.

        Returns:
            Any unexplored strict superset of seed, if one exists.
        """
        superset_exists = self.solver.solve(seed)
        if superset_exists:
            return self.get_seed()
        else:
            return None

    def get_seed(self):
        """Get the seed from the current model.  (Depends on work in next_seed to be valid.)

        Returns:
            A seed as an array of 1-based constraint indexes.
        """
        return self.solver.get_model_trues(start=0, end=self.n, offset=1)

        # slower:
        #model = self.solver.get_model()
        #return [i for i in range(self.n) if model[i]]

        # slowest:
        #seed = []
        #for i in range(self.n):
        #    if self.solver.model_value(i+1):
        #        seed.add(i)
        #return seed

    def maximize_seed(self, seed, direction):
        """Maximize a given seed within the current set of constraints.
           The Boolean direction parameter specifies up (True) or down (False)

        Returns:
            A seed as an array of 1-based constraint indexes.
        """
        while True:
            comp = self.complement(seed)
            tmpvar = self.solver.new_var() + 1
            if direction:
                # search for a solution w/ all of the current seed plus at
                # least one from the current complement.
                self.solver.add_clause([-tmpvar] + list(comp))  # temporary clause
                # activate the temporary clause and all seed clauses
                havenew = self.solver.solve([tmpvar] + list(seed))
            else:
                # search for a solution w/ none of current complement and at
                # least one from the current seed removed.
                self.solver.add_clause([-tmpvar] + [-i for i in seed])  # temporary clause
                # activate the temporary clause and deactivate complement clauses
                havenew = self.solver.solve([tmpvar] + [-i for i in comp])
            self.solver.add_clause([-tmpvar])  # remove the temporary clause

            if havenew:
                seed = self.get_seed()
            else:
                return seed

    def complement(self, aset):
        """Return the complement of a given set w.r.t. the set of mapped constraints."""
        return self.all_n.difference(aset)

    def add_clause(self, clause):
        """Add a given clause to the Map solver."""
        self.solver.add_clause(clause)
        if self.dump is not None:
            self.dump.write(" ".join(str(lit) for lit in clause) + " 0\n")

    def block_down(self, frompoint):
        """Block down from a given set."""
        clause = self.complement(frompoint)
        self.add_clause(clause)

    def block_up(self, frompoint):
        """Block up from a given set."""
        clause = [-i for i in frompoint]
        self.add_clause(clause)


class MinicardMapSolver(MapSolver):
    def __init__(self, n, bias=True):   # bias=True is a high/inclusion/MUS bias; False is a low/exclusion/MSS bias.
        super(MinicardMapSolver, self).__init__(n, bias)

        if bias:
            self.k = n  # initial lower bound on # of True variables
        else:
            self.k = 0

        self._solver = minisolvers.MinicardSolver()

        while self.solver.nvars() < self.n:
            self.solver.new_var(self.bias)

        # add "bound-setting" variables
        while self.solver.nvars() < self.n*2:
            self.solver.new_var()

        # add cardinality constraint (comment is for high bias, maximal model;
        #                             becomes AtMostK for low bias, minimal model)
        # want: generic AtLeastK over all n variables
        # how: make AtLeast([n vars, n bound-setting vars], n)
        #      then, assume the desired k out of the n bound-setting vars.
        # e.g.: for real vars a,b,c: AtLeast([a,b,c, x,y,z], 3)
        #       for AtLeast 3: assume(-x,-y,-z)
        #       for AtLeast 1: assume(-x)
        # and to make AtLeast into an AtMost:
        #   AtLeast([lits], k) ==> AtMost([-lits], #lits-k)
        if self.bias:
            self.solver.add_atmost([-(x+1) for x in range(self.n * 2)], self.n)
        else:
            self.solver.add_atmost([(x+1) for x in range(self.n * 2)], self.n)

    @property
    def solver(self):
        return self._solver

    def solve_with_bound(self, k):
        # same assumptions work both for high bias / atleast and for low bias / atmost
        return self.solver.solve( [-(self.n+x+1) for x in range(k)] + [(self.n+k+x+1) for x in range(self.n-k)] )

    def next_seed(self):
        '''
            Find the next *maximum* model.
        '''
        if self.solve_with_bound(self.k):
            return self.get_seed()

        if self.bias:
            if not self.solve_with_bound(0):
                # no more models
                return None
            # move to the next bound
            self.k -= 1
        else:
            if not self.solve_with_bound(self.n):
                # no more models
                return None
            # move to the next bound
            self.k += 1

        while not self.solve_with_bound(self.k):
            if self.bias:
                self.k -= 1
            else:
                self.k += 1

        assert 0 <= self.k <= self.n

        return self.get_seed()

    def block_above_size(self, size):
        self.solver.add_atmost( [(x+1) for x in range(self.n)], size)
        self.k = min(size, self.k)

    def block_below_size(self, size):
        self.solver.add_atmost( [-(x+1) for x in range(self.n)], self.n-size)
        self.k = min(size, self.k)


class MinisatMapSolver(MapSolver):
    def __init__(self, n, bias=True, dump=None):   # bias=True is a high/inclusion/MUS bias; False is a low/exclusion/MSS bias; None is no bias.
        super(MinisatMapSolver, self).__init__(n, bias, dump)

        self._solver = minisolvers.MinisatSolver()
        while self.solver.nvars() < self.n:
            self.solver.new_var(self.bias)

        if self.bias is None:
            self.solver.set_rnd_pol(True)

    @property
    def solver(self):
        return self._solver

    def next_seed(self):
        if self.solver.solve():
            return self.get_seed()
        else:
            return None
