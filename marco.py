#!/usr/bin/env python

import argparse
import os
import sys

import mapsolvers
import utils
from MarcoPolo import MarcoPolo

def setup():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="print more verbose output (constraint indexes)")
    parser.add_argument('-l', '--limit', type=int, default=None,
                        help="limit number of subsets output (counting both MCSes and MUSes)")
    parser.add_argument('-m', '--max-seed', action='store_true',
                        help="always find a maximal/minimal seed, controlled by bias setting (high=maximal, low=minimal) (uses MiniCard as Map solver)")
    parser.add_argument('-b', '--bias', type=str, choices=['high','low'], default='high',
                        help="bias the Map solver toward unsatisfiable seeds (high) or satisfiable seeds (low) (default: high, which is best for enumerating MUSes)")
    parser.add_argument('--smus', action='store_true',
                        help="calculate an SMUS (smallest MUS) ; implies -m")
    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument('--cnf', action='store_true',
                        help="Treat input as DIMACS CNF format.")
    type_group.add_argument('--smt', action='store_true',
                        help="Treat input as SMT2 format.")
    parser.add_argument('--force-minisat', action='store_true',
                        help="use Minisat in place of MUSer2 for CNF (NOTE: much slower and usually not worth doing!)")
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'),
                        default=sys.stdin,
                        help="name of file to process (STDIN if omitted)")
    args = parser.parse_args()

    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    infile = args.infile

    if args.smt and infile == sys.stdin:
        print >>sys.stderr, "SMT cannot be read from STDIN.  Please specify a filename."
        sys.exit(1)

    # create appropriate constraint solver
    if args.cnf or infile.name.endswith('.cnf') or infile.name.endswith('.cnf.gz'):
        if args.force_minisat:
            from MinisatSubsetSolver import MinisatSubsetSolver
            csolver = MinisatSubsetSolver(infile)
            infile.close()
        else:
            try:
                from MUSerSubsetSolver import MUSerSubsetSolver
                csolver = MUSerSubsetSolver(infile)
            except Exception as e:
                print >>sys.stderr, "ERROR: Unable to use MUSer2 for MUS extraction.\n\n%s\n\nUse --force-minisat to use Minisat instead (NOTE: it will be much slower.)" % str(e)
                sys.exit(1)
            
        infile.close()
    elif args.smt or infile.name.endswith('.smt2') or infile.name.endswith('.smt2.gz'):
        try:
            from Z3SubsetSolver import Z3SubsetSolver
        except ImportError as e:
            print >>sys.stderr, "ERROR: Unable to import z3 module:  %s\n\nPlease install Z3 from https://z3.codeplex.com/" % str(e)
            sys.exit(1)
        # z3 has to be given a filename, not a file object, so close infile and just pass its name
        infile.close()
        csolver = Z3SubsetSolver(infile.name)
    else:
        print >>sys.stderr, \
            "Cannot determine filetype (cnf or smt) of input: %s\n" \
            "Please provide --cnf or --smt option." % infile.name
        sys.exit(1)

    # setup config
    config = {}
    config['smus'] = args.smus
    config['bias'] = (args.bias == 'high')
    config['limit'] = args.limit
    config['verbose'] = args.verbose

    # create appropriate map solver
    if args.max_seed or args.smus:
        msolver = mapsolvers.MinicardMapSolver(n=csolver.n, bias=config['bias'])
    else:
        msolver = mapsolvers.MinisatMapSolver(n=csolver.n, bias=config['bias'])

    return (csolver, msolver, config)

def main():
    timer = utils.Timer()

    with timer.measure('setup'):
        (csolver, msolver, config) = setup()

        # create a MarcoPolo instance with the constraint solver
        mp = MarcoPolo(csolver, msolver, timer, config)

    # useful for timing just the parsing / setup
    if config['limit'] == 0:
        return

    # enumerate results
    remaining = config['limit']
    for result in mp.enumerate():
        if config['verbose']:
            print result[0], " ".join([str(x+1) for x in result[1]])
        else:
            print result[0]

        if remaining:
            remaining -= 1
            if remaining == 0: break

    print timer.get_times()

if __name__ == '__main__':
    main()

