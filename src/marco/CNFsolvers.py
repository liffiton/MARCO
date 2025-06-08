import atexit
import bisect
import collections
import gzip
import os
import re
import subprocess
import tempfile

from . import utils
from ..pyminisolvers import minisolvers


class MinisatSubsetSolver(object):
    def __init__(self, filename, rand_seed=None, n_only=False, store_dimacs=False):
        self.s = minisolvers.MinisatSubsetSolver()

        # Initialize random seed and randomize variable activity if seed is given
        if rand_seed is not None:
            self.s.set_rnd_seed(rand_seed)
            self.s.set_rnd_init_act(True)

        self.n_only = n_only

        self.store_dimacs = store_dimacs
        if self.store_dimacs:
            self.dimacs = []
            self.groups = collections.defaultdict(list)
        self.read_dimacs(filename)
        self._msolver = None

    def set_msolver(self, msolver):
        self._msolver = msolver

    def parse_dimacs(self, f):
        i = 0
        for line in f:
            if line.startswith(b'p'):
                tokens = line.split()
                gcnf_in = (tokens[1] == b"gcnf")
                self.nvars = int(tokens[2])
                self.nclauses = int(tokens[3])

                # self.n = number of soft constraints
                if gcnf_in:
                    self.n = int(tokens[4])
                else:
                    self.n = self.nclauses

                if self.n_only:
                    # We're only here to parse the number of constraints.  Bail now.
                    return

                self.s.set_varcounts(self.nvars, self.n)

                # let instance variables do whatever...
                self.s.new_vars(self.nvars)
                # but default relaxation variables to try to *enable*
                # clauses (to find larger sat subsets and/or hit unsat
                # sooner)
                self.s.new_vars(self.n, True)

                continue

            if line.startswith(b'c'):
                continue

            line = line.strip()
            if line == b'':
                continue

            # anything else is a clause
            assert self.n > 0
            vals = line.split()
            assert vals[-1] == b'0'

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
                    self.dimacs.append(b" ".join(str(x).encode() for x in clause) + b" 0\n")
                    self.groups[groupid].append(i)
                else:
                    self.dimacs.append(line + b"\n")
                    self.groups[groupid] = [i]

            i += 1

        assert i == self.nclauses

    def read_dimacs(self, filename):
        if filename.endswith('.gz'):
            # use gzip to decompress
            with gzip.open(filename, 'rb') as gz_f:
                self.parse_dimacs(gz_f)
        else:
            # assume plain .cnf and pass through the file object
            with open(filename, 'rb') as f:
                self.parse_dimacs(f)

    def check_subset(self, seed, improve_seed=False):
        is_sat = self.s.solve_subset([i-1 for i in seed])
        if improve_seed:
            if is_sat:
                seed = self.s.sat_subset(offset=1)
            else:
                seed = self.s.unsat_core(offset=1)
            return is_sat, seed
        else:
            return is_sat

    def complement(self, aset):
        return set(range(1, self.n+1)).difference(aset)

    def shrink(self, seed):
        hard = self._msolver.implies()
        current = set(seed)
        for i in seed:
            if i not in current or i in hard:
                # May have been "also-removed"
                continue
            current.remove(i)
            if not self.check_subset(current):
                # Remove any also-removed constraints
                current = set(self.s.unsat_core(offset=1))  # helps a bit
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

    def grow(self, seed):
        current = seed

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
                current = self.s.sat_subset(offset=1)
            else:
                current.pop()

        return current


class MUSerSubsetSolver(MinisatSubsetSolver):
    def __init__(self, filename, rand_seed=None, n_only=False):
        MinisatSubsetSolver.__init__(self, filename, rand_seed, n_only, store_dimacs=True)
        self.core_pattern = re.compile(r'^v [\d ]+$', re.MULTILINE)

        binary = 'muser2-para'
        self.muser_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), binary)
        utils.check_executable("MUSer2", self.muser_path)

        self._proc = None  # track the MUSer process
        atexit.register(self.cleanup)

    # kill MUSer process if still running when we exit (e.g. due to a timeout)
    def cleanup(self):
        if self._proc:
            self._proc.kill()

    # write CNF output for MUSer2
    def write_CNF(self, cnffile, seed, hard):
        # Write CNF (grouped, with hard clauses, if any, in the 0 / Don't-care group)
        header = "p gcnf %d %d %d\n" % (self.nvars, len(seed), len(seed))
        cnffile.write(header.encode())

        # Note: not writing newlines because dimacs[j] already contains a newline

        # existing "Don't care" group
        for j in self.groups[0]:
            cnffile.write(b"{0} ")  # {0} = "Don't care" group
            cnffile.write(self.dimacs[j])
        # also include hard clauses in "Don't care" group
        for i in hard:
            for j in self.groups[i]:
                cnffile.write(b"{0} ")
                cnffile.write(self.dimacs[j])

        for g, i in enumerate(seed):
            if i in hard:
                # skip hard clauses
                continue
            for j in self.groups[i]:
                cnffile.write(("{%d} " % (g+1)).encode())
                cnffile.write(self.dimacs[j])

        cnffile.flush()

    # override shrink method to use MUSer2
    # NOTE: seed must be indexed (i.e., not a set)
    def shrink(self, seed):
        hard = [x for x in self._msolver.implies() if x > 0]
        # In parallel mode, this seed may be explored by the time
        # we get here.  If it is, the hard constraints may include
        # constraints *outside* of the current seed, which would invalidate
        # the returned MUS.  If the seed is explored, give up on this seed.
        if not self._msolver.check_seed(seed):
            return None

        # MUSer doesn't like a formula with only hard constraints,
        # and it's a waste of time to call MUSer at all on it anyway.
        if len(seed) == len(hard):
            return seed

        # Open tmpfile
        with tempfile.NamedTemporaryFile('wb') as cnf:
            self.write_CNF(cnf, seed, hard)
            args = [self.muser_path, '-comp', '-grp', '-v', '-1']
            args += [cnf.name]

            # Run MUSer
            self._proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = self._proc.communicate()
            self._proc = None  # clear it when we're done (so cleanup won't try to kill it)

            out = out.decode()

        # Parse result, return the core
        matchline = re.search(self.core_pattern, out).group(0)
        # pMUSer outputs 0 groups as part of MUSes, so we'll just filter it out to prevent the
        # duplicate clauses in MUSes
        ret = [seed[int(x)-1] for x in matchline.split()[1:-1] if int(x) > 0]

        # Add back in hard clauses
        ret.extend(hard)

        assert len(ret) <= len(seed)

        return ret


class ImprovedImpliesSubsetSolver(MinisatSubsetSolver):
    def __init__(self, filename, rand_seed=None, n_only=False, store_dimacs=False):
        MinisatSubsetSolver.__init__(self, filename, rand_seed, n_only, store_dimacs)
        self._known_MSS = 0
        self._known_MUS = 0

    def increment_MSS(self):
        self._known_MSS += 1

    def increment_MUS(self):
        self._known_MUS += 1

    def shrink(self, seed):
        current = set(seed)

        if self._known_MSS > 0:
            implications = self._msolver.implies(-x for x in self.complement(current))
            hard = set(x for x in implications if x > 0)
        else:
            hard = set()

        for i in seed:
            if i not in current or i in hard:
                continue
            current.remove(i)

            if self.check_subset(current):
                current.add(i)
            else:
                current = set(self.s.unsat_core(offset=1))
                if self._known_MSS > 0:
                    implications = self._msolver.implies(-x for x in self.complement(current))
                    hard = set(x for x in implications if x > 0)

        return current

    def grow(self, seed):
        current = set(seed)

        if self._known_MUS > 0:
            implications = self._msolver.implies(current)
            dont_add = set(x for x in implications if x < 0)
        else:
            dont_add = set()

        for i in self.complement(current):
            if i in current or i in dont_add:
                continue
            current.add(i)

            if not self.check_subset(current):
                current.remove(i)
            else:
                current = set(self.s.sat_subset(offset=1))
                if self._known_MUS > 0:
                    implications = self._msolver.implies(current)
                    dont_add = set(x for x in implications if x < 0)

        return current
