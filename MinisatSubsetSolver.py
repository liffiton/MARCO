import gzip
import re
import bisect
from pyminisolvers import minisolvers

class MinisatSubsetSolver:
    def __init__(self, infile, store_dimacs=False):
        self.s = minisolvers.MinisatSubsetSolver()
        self.store_dimacs = store_dimacs
        if self.store_dimacs:
            self.dimacs = []
        self.read_dimacs(infile)

    def parse_dimacs(self, f):
        i = 0
        for line in f:
            if line.startswith(b'p'):
                pattern = re.compile(r'p\s+cnf\s+(\d+)\s+(\d+)')
                matches = re.match(pattern, line.decode()).groups()
                self.nvars = int(matches[0])
                self.n = int(matches[1])
                self.s.set_orig(self.nvars, self.n)
                while self.s.nvars() < self.nvars:
                    # let instance variable do whatever...
                    self.s.new_var()
                while self.s.nvars() < self.nvars + self.n:
                    # but default relaxation variables to try to *enable*
                    # clauses (to find larger sat subsets and/or hit unsat
                    # sooner)
                    self.s.new_var(True)
                continue
            if line.startswith(b'c'):
                continue
            assert self.n > 0
            self.s.add_clause_instrumented([int(x) for x in line.split()[:-1]])
            i += 1
            if self.store_dimacs:
                self.dimacs.append(line)
        assert i == self.n

    def read_dimacs(self, infile):
        if infile.name.endswith('.gz'):
            # use gzip to decompress
            infile.close()
            with gzip.open(infile.name) as gz_f:
                self.parse_dimacs(gz_f)
        else:
            # assume plain .cnf and pass through the file object
            self.parse_dimacs(infile)

    def check_subset(self, seed, improve_seed=False):
        is_sat = self.s.solve_subset(seed)
        if improve_seed:
            if is_sat:
                seed = self.s.sat_subset()
            else:
                seed = self.s.unsat_core()
            return is_sat, seed
        else:
            return is_sat

    def complement(self, aset):
        return set(range(self.n)).difference(aset)

    def shrink(self, seed):
        current = set(seed)
        for i in seed:
            if i not in current:
                # May have been "also-removed"
                continue
            current.remove(i)
            if not self.check_subset(current):
                # Remove any also-removed constraints
                current = set(self.s.unsat_core())  # helps a bit
            else:
                current.add(i)
        return current
        
    def to_c_lits(self, seed):
        # this is slow...
        nv = self.nvars+1
        return [nv + i for i in seed]

    def check_above(self, seed):
        comp = self.complement(seed)
        x = self.s.new_var() + 1
        self.s.add_clause([-x] + self.to_c_lits(comp))  # add a temporary clause
        ret = self.s.solve([x] + self.to_c_lits(seed))  # activate the temporary clause and all seed clauses
        self.s.add_clause([-x])  # remove the temporary clause
        return ret

    def grow(self, seed, inplace):
        if inplace:
            current = seed
        else:
            current = seed[:]

        #while self.check_above(current):
        #    current = self.s.sat_subset()
        #return current

        # a bit slower at times, much faster others...
        for x in self.complement(current):
            # skip any included by sat_subset()
            # assumes seed is always sorted
            i = bisect.bisect_left(current, x)
            if i != len(current) and current[i] == x:
                continue

            current.append(x)
            if self.check_subset(current):
                # Add any also-satisfied constraint
                current = self.s.sat_subset()
            else:
                current.pop()

        return current

