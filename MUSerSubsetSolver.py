import os
import tempfile
import subprocess
from MinisatSubsetSolver import MinisatSubsetSolver

class MUSerSubsetSolver(MinisatSubsetSolver):
    def __init__(self, filename):
        MinisatSubsetSolver.__init__(self, filename, store_dimacs=True)

    # override shrink method to use MUSer2
    def shrink(self, seed):
        muser_path = './muser2-static'
        # Open tmpfile
        with tempfile.NamedTemporaryFile(delete=False) as cnf:
            # Write CNF
            print >>cnf, "p cnf %d %d" % (self.nvars, len(seed))
            for i in seed:
                print >>cnf, self.dimacs[i],  # dimacs[i] has newline
            cnf.flush()
            # Run MUSer
            p = subprocess.Popen([muser_path, '-comp', '-v', '-1', cnf.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out,err = p.communicate()
            result = out

        # Parse result
        import re
        pattern = re.compile(r'^v [\d ]+$', re.MULTILINE)
        matchline = re.search(pattern, result).group(0)
        core = [seed[int(x)-1] for x in matchline.split()[1:-1]]
        return core

