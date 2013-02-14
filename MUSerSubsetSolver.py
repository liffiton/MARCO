import os
import subprocess
from MinisatSubsetSolver import MinisatSubsetSolver

class MUSerSubsetSolver(MinisatSubsetSolver):
    def __init__(self, filename):
        MinisatSubsetSolver.__init__(self, filename, store_dimacs=True)

    # override shrink method to use MUSer2
    def shrink(self, seed):
        tmpfile_path = '/tmp/musertmpfile'
        muser_path = '/home/liffiton/research/solvers/muser2-src/src/tools/muser-2/muser-2'
        # Create tmpfile
        #os.mktmpfile(tmpfile_path)
        # Open tmpfile
        with open(tmpfile_path,'w') as cnf:
            # Write CNF
            print >>cnf, "p cnf %d %d" % (self.nvars, len(seed))
            for i in seed:
                print >>cnf, self.dimacs[i-1],  # dimacs[i] has newline
        # Run MUSer
        p = subprocess.Popen([muser_path, '-v', '-1', tmpfile_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out,err = p.communicate()
        result = out

        # Unlink tmpfile
        os.unlink(tmpfile_path)

        # Parse result
        import re
        pattern = re.compile(r'^v [\d ]+$', re.MULTILINE)
        matchline = re.search(pattern, result).group(0)
        core = [seed[int(x)-1] for x in matchline.split()[1:-1]]
        return core

