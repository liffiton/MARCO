import re
import os
import tempfile
import subprocess
from MinisatSubsetSolver import MinisatSubsetSolver

class MUSerSubsetSolver(MinisatSubsetSolver):
    def __init__(self, filename):
        MinisatSubsetSolver.__init__(self, filename, store_dimacs=True)
        self.core_pattern = re.compile(r'^v [\d ]+$', re.MULTILINE)
        self.muser_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'muser2-static')
        if not os.path.isfile(self.muser_path):
            raise Exception("MUSer2 binary not found at %s" % self.muser_path)
        try:
            # a bit of a hack to check whether we can really run it
            DEVNULL = open(os.devnull, 'wb')
            p = subprocess.Popen([self.muser_path], stdout=DEVNULL, stderr=DEVNULL)
        except:
            raise Exception("MUSer2 binary %s is not executable.\nIt may be compiled for a different platform." % self.muser_path)

    # override shrink method to use MUSer2
    def shrink(self, seed):
        seed = list(seed)  # need to look up clauses from MUS as indexes into this list
        # Open tmpfile
        with tempfile.NamedTemporaryFile('wb') as cnf:
            # Write CNF
            header = "p cnf %d %d\n" % (self.nvars, len(seed))
            cnf.write(header.encode())
            for i in seed:
                cnf.write(self.dimacs[i])  # dimacs[i] has newline
            cnf.flush()
            # Run MUSer
            p = subprocess.Popen([self.muser_path, '-comp', '-v', '-1', cnf.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out,err = p.communicate()
            result = out.decode()

        # Parse result
        matchline = re.search(self.core_pattern, result).group(0)
        core = [seed[int(x)-1] for x in matchline.split()[1:-1]]
        return core

