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
                        help="limit the runtime to TIMEOUT seconds")
    parser.add_argument('-l', '--limit', type=int, default=None,
                        help="limit number of subsets output (counting both MCSes and MUSes)")
    parser.add_argument('-b', '--bias', type=str, choices=['high','low'], default='high',
                        help="bias the Map solver toward unsatisfiable seeds (high) or satisfiable seeds (low) (default: high, which is best for enumerating MUSes)")
    max_group = parser.add_mutually_exclusive_group()
    max_group.add_argument('--half-max', action='store_true',
                        help="only compute a maximal model if the initial seed is SAT / bias is high or seed is UNSAT /bias is low")
    max_group.add_argument('-m', '--max-seed', action='store_true',
                        help="always find a maximal/minimal seed (local optimum), controlled by bias setting (high=maximal, low=minimal)")
    max_group.add_argument('-M', '--maximum-seed', action='store_true',
                        help="always find a maximum/minimum seed (largest/smallest cardinality), controlled by bias setting (high=maximum, low=minimum) (uses MiniCard as Map solver)")
    parser.add_argument('--smus', action='store_true',
                        help="calculate an SMUS (smallest MUS)")
    parser.add_argument('--mssguided', action='store_true',
                        help="check for unexplored subsets in immediate supersets of any MSS found")
    parser.add_argument('--nogrow', action='store_true',
                        help="do not grow any satisfiable subsets found, just block as-is")
    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument('--cnf', action='store_true',
                        help="assume input is in DIMACS CNF or Group CNF format (autodetected if filename is *.[g]cnf or *.[g]cnf.gz).")
    type_group.add_argument('--smt', action='store_true',
                        help="assume input is in SMT2 format (autodetected if filename is *.smt2).")
    parser.add_argument('--force-minisat', action='store_true',
                        help="use Minisat in place of MUSer2 for CNF (NOTE: much slower and usually not worth doing!)")
    parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'),
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
    # print stats
    times = timer.get_times()
    counts = timer.get_counts()
    # sort categories by total runtime
    categories = sorted(times, key=times.get)
    maxlen = max(len(x) for x in categories)
    for category in categories:
        sys.stderr.write("%-*s : %8.3f\n" % (maxlen, category, times[category]))
    for category in categories:
        if category in counts and counts[category] > 1:
            sys.stderr.write("%-*s : %8d\n" % (maxlen + 6, category + " count", counts[category]))
            sys.stderr.write("%-*s : %8.5f\n" % (maxlen + 6, category + " per", times[category]/counts[category]))

def setup_execution(args, timer):
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

    # register a timeout alarm, if needed
    if args.timeout:
        signal.signal(signal.SIGALRM, handler)  # timeout alarm
        signal.alarm(args.timeout)
    
    # register at_exit to print stats when program exits
    if args.stats:
        atexit.register(at_exit, timer)


def setup_solvers(args):
    infile = args.infile

    # create appropriate constraint solver
    if args.cnf or infile.name.endswith('.cnf') or infile.name.endswith('.cnf.gz') or infile.name.endswith('.gcnf') or infile.name.endswith('.gcnf.gz'):
        if args.force_minisat:
            from MinisatSubsetSolver import MinisatSubsetSolver
            csolver = MinisatSubsetSolver(infile)
            infile.close()
        else:
            try:
                from MUSerSubsetSolver import MUSerSubsetSolver, MUSerException
                csolver = MUSerSubsetSolver(infile)
            except MUSerException as e:
                sys.stderr.write("[31;1mERROR:[m Unable to use MUSer2 for MUS extraction.\n[33mUse --force-minisat to use Minisat instead[m (NOTE: it will be much slower.)\n\n")
                sys.stderr.write(str(e) + "\n")
                sys.exit(1)
            
        infile.close()
    elif args.smt or infile.name.endswith('.smt2'):
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
    if args.maximum_seed or args.smus:
        from mapsolvers import MinicardMapSolver
        msolver = MinicardMapSolver(n=csolver.n, bias=varbias)
    else:
        from mapsolvers import MinisatMapSolver
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
        if args.max_seed:
            config['maxseed'] = 'always'
        elif args.maximum_seed:
            config['maxseed'] = 'optimum'
        elif args.half_max:
            config['maxseed'] = 'half'
        else:
            config['maxseed'] = None
        config['mssguided'] = args.mssguided
        config['nogrow'] = args.nogrow
        config['half_max'] = args.half_max

        mp = MarcoPolo(csolver, msolver, timer, config)

    # useful for timing just the parsing / setup
    if args.limit == 0:
        sys.stderr.write("Result limit reached.\n")
        sys.exit(0)

    # enumerate results
    remaining = args.limit

    for result in mp.enumerate():
        if args.verbose:
            output = "%s %s" % (result[0], " ".join([str(x+1) for x in result[1]]))
            print(output)
        else:
            print(result[0])

        if remaining:
            remaining -= 1
            if remaining == 0:
                sys.stderr.write("Result limit reached.\n")
                sys.exit(0)


if __name__ == '__main__':
    main()

