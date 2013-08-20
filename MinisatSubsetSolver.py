import collections
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
            self.groups = collections.defaultdict(list)
        self.read_dimacs(infile)

    def parse_dimacs(self, f):
        i = 0
        for line in f:
            if line.startswith(b'p'):
                tokens = line.split()
                gcnf_in = (tokens[1] == "gcnf")
                self.nvars = int(tokens[2])
                self.nclauses = int(tokens[3])

                # self.n = number of soft constraints
                if gcnf_in:
                    self.n = int(tokens[4])
                else:
                    self.n = self.nclauses

                self.s.set_varcounts(self.nvars, self.n)

                while self.s.nvars() < self.nvars:
                    # let instance variables do whatever...
                    self.s.new_var()
                while self.s.nvars() < self.nvars + self.n:
                    # but default relaxation variables to try to *enable*
                    # clauses (to find larger sat subsets and/or hit unsat
                    # sooner)
                    self.s.new_var(True)
                continue

            if line.startswith(b'c'):
                continue

            # anything else is a clause
            assert self.n > 0
            vals = line.split()
            assert vals[-1] == '0'

            if gcnf_in:
                groupid = int(vals[0][1:-1])  # "parse" the '{x}' group ID
                assert 0 <= groupid <= self.n
                clause = [int(x) for x in vals[1:-1]]
            else:
                groupid = i+1
                clause = [int(x) for x in vals[:-1]]

            if groupid == 0:
                # add as a hard clause
                self.s.add_clause(clause)
            else:
                self.s.add_clause_instrumented(clause, groupid-1)

            if self.store_dimacs:
                if gcnf_in:
                    # need to reform clause without '{x}' group index
                    self.dimacs.append(" ".join(str(x) for x in clause) + " 0\n")
                    self.groups[groupid].append(i)
                else:
                    self.dimacs.append(line)
                    self.groups[groupid] = [i]

            i += 1

        assert i == self.nclauses

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

    def shrink(self, seed, hard=[]):
        current = set(seed)
        for i in seed:
            if i not in current or i in hard:
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
