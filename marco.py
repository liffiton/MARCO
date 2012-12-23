#!/usr/bin/env python

import os
import sys
from MarcoPolo import MarcoPolo
from MinisatMapSolver import MinisatMapSolver
#from Z3MapSolver import Z3MapSolver

def main():
    if len(sys.argv) < 2:
        print "Usage: %s FILE.[smt2,cnf]" % sys.argv[0]
        sys.exit(1)

    filename = sys.argv[1]
    if not os.path.exists(filename):
        print "File does not exist: %s" % filename
        sys.exit(1)

    if len(sys.argv) > 2:
        limit = int(sys.argv[2])
    else:
        limit = None

    if filename.endswith('.cnf'):
        from MinisatSubsetSolver import MinisatSubsetSolver
        csolver = MinisatSubsetSolver(filename)
    else:
        from Z3SubsetSolver import Z3SubsetSolver
        csolver = Z3SubsetSolver(filename)

    msolver = MinisatMapSolver(csolver.n)

    mp = MarcoPolo(csolver, msolver)

    if limit == 0:
        # useful for timing just the parsing / setup
        return

    for result in mp.enumerate():
        print result[0], len(result[1])

        if limit:
            limit -= 1
            if limit == 0: break

if __name__ == '__main__':
    main()

