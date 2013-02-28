#!/usr/bin/env python

import argparse
import os
import sys
from MarcoPolo import MarcoPolo

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--limit', type=int, default=None,
                        help="limit number of subsets output (MCSes and MUSes)")
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'),
                        default=sys.stdin,
                        help="name of file to process (STDIN if omitted)")
    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument('--cnf', action='store_true')
    type_group.add_argument('--smt', action='store_true')
    args = parser.parse_args()

    infile = args.infile

    if args.smt and infile == sys.stdin:
        print >>sys.stderr, "SMT cannot be read from STDIN.  Please specify a filename."
        system.exit(1)

    # create appropriate constraint solver
    if args.cnf or infile.name.endswith('.cnf') or infile.name.endswith('.cnf.gz'):
        from MUSerSubsetSolver import MUSerSubsetSolver
        csolver = MUSerSubsetSolver(infile)
        infile.close()
    elif args.smt or infile.name.endswith('.smt2') or infile.name.endswith('.smt2.gz'):
        # z3 has to be given a filename, not a file object, so close infile and just pass its name
        infile.close()
        from Z3SubsetSolver import Z3SubsetSolver
        csolver = Z3SubsetSolver(infile.name)
    else:
        print >>sys.stderr, \
            "Cannot determine filetype (cnf or smt) of input: %s\n" \
            "Please provide --cnf or --smt option." % infile.name
        sys.exit(1)

    # create a MarcoPolo instance with the constraint solver
    mp = MarcoPolo(csolver)

    # useful for timing just the parsing / setup
    if args.limit == 0:
        return

    # enumerate results
    lim = args.limit
    for result in mp.enumerate():
        print result[0]  #, len(result[1])

        if lim:
            lim -= 1
            if lim == 0: break

if __name__ == '__main__':
    main()

