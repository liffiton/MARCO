import re
import os
import tempfile
import subprocess
import atexit
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

        self._proc = None  # track the MUSer process
        atexit.register(self.cleanup)

    # kill MUSer process if still running when we exit (e.g. due to a timeout)
    def cleanup(self):
        if self._proc:
            self._proc.kill()

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
            self._proc = subprocess.Popen([self.muser_path, '-comp', '-v', '-1', cnf.name],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out,err = self._proc.communicate()
            self._proc = None  # clear it when we're done (so cleanup won't try to kill it)
            out = out.decode()

        # Parse result, return the core
        matchline = re.search(self.core_pattern, out).group(0)
        return set( seed[int(x)-1] for x in matchline.split()[1:-1] )

