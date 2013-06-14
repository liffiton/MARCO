#!/usr/bin/env python

import argparse
import atexit
import os
import signal
import sys

import utils
from MarcoPolo import MarcoPolo

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="print more verbose output (constraint indexes)")
    parser.add_argument('-s', '--stats', action='store_true',
                        help="print timing statistics to stderr")
    parser.add_argument('-T', '--timeout', type=int, default=None,
                        help="limit the runtime to N seconds")
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

    if args.smt and args.infile == sys.stdin:
        sys.stderr.write("SMT cannot be read from STDIN.  Please specify a filename.\n")
        sys.exit(1)

    return args

def at_exit(timer):
    times = timer.get_times()
    for category, time in times.items():
        sys.stderr.write("%10s : %8.2f\n" % (category, time))

def setup_execution(args, timer):
    # register at_exit to print stats when program exits
    if args.stats:
        atexit.register(at_exit, timer)

    # register timeout/interrupt handler
    def handler(signum, frame):
        if signum == signal.SIGALRM:
            sys.stderr.write("Time limit reached.\n")
        else:
            sys.stderr.write("Interrupted.\n")
        sys.exit(128)
        # at_exit will fire here

    signal.signal(signal.SIGTERM, handler)  # external termination
    signal.signal(signal.SIGINT, handler)   # ctl-c keyboard interrupt
    signal.signal(signal.SIGALRM, handler)  # timeout alarm

    # register a timeout alarm, if needed
    if args.timeout:
        signal.alarm(args.timeout)

def setup_solvers(args):
    infile = args.infile

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
                sys.stderr.write("ERROR: Unable to use MUSer2 for MUS extraction.\n\n%s\n\nUse --force-minisat to use Minisat instead (NOTE: it will be much slower.)\n" % str(e))
                sys.exit(1)
            
        infile.close()
    elif args.smt or infile.name.endswith('.smt2') or infile.name.endswith('.smt2.gz'):
        try:
            from Z3SubsetSolver import Z3SubsetSolver
        except ImportError as e:
            sys.stderr.write("ERROR: Unable to import z3 module:  %s\n\nPlease install Z3 from https://z3.codeplex.com/\n" % str(e))
            sys.exit(1)
        # z3 has to be given a filename, not a file object, so close infile and just pass its name
        infile.close()
        csolver = Z3SubsetSolver(infile.name)
    else:
        sys.stderr.write(
            "Cannot determine filetype (cnf or smt) of input: %s\n" \
            "Please provide --cnf or --smt option.\n" % infile.name
        )
        sys.exit(1)

    # create appropriate map solver
    varbias = (args.bias == 'high')
    if args.max_seed or args.smus:
        from mapsolvers import MinicardMapSolver
        msolver  = MinicardMapSolver(n=csolver.n, bias=varbias)
    else:
        from mapsolvers import MinisatMapSolver
        #import trace_calls
        #trace_calls.trace_class(MinisatMapSolver)
        msolver = MinisatMapSolver(n=csolver.n, bias=varbias)

    return (csolver, msolver)

def main():
    timer = utils.Timer()

    with timer.measure('setup'):
        args = parse_args()

        setup_execution(args, timer)

        (csolver, msolver) = setup_solvers(args)

        config = {}
        config['smus'] = args.smus
        config['bias'] = args.bias
        config['maxseed'] = args.max_seed

        mp = MarcoPolo(csolver, msolver, timer, config)

    # useful for timing just the parsing / setup
    if args.limit == 0:
        sys.stderr.write("Result limit reached.\n")
        sys.exit(0)

    # enumerate results
    remaining = args.limit
    for result in mp.enumerate():
        if args.verbose:
            print result[0], " ".join([str(x+1) for x in result[1]])
        else:
            print result[0]

        if remaining:
            remaining -= 1
            if remaining == 0:
                sys.stderr.write("Result limit reached.\n")
                sys.exit(0)


if __name__ == '__main__':
    main()

