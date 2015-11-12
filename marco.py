#!/usr/bin/env python

import argparse
import atexit
import signal
import sys
import threading

import utils
import mapsolvers
import CNFsolvers
from MarcoPolo import MarcoPolo


def parse_args():
    parser = argparse.ArgumentParser()

    # Standard arguments
    parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'),
                        default=sys.stdin,
                        help="name of file to process (STDIN if omitted)")
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="print more verbose output (constraint indexes for MUSes/MCSes) -- repeat the flag for detail about the algorithm's progress)")
    parser.add_argument('-a', '--alltimes', action='store_true',
                        help="print the time for every output")
    parser.add_argument('-s', '--stats', action='store_true',
                        help="print timing statistics to stderr")
    parser.add_argument('-T', '--timeout', type=int, default=None,
                        help="limit the runtime to TIMEOUT seconds")
    parser.add_argument('-l', '--limit', type=int, default=None,
                        help="limit number of subsets output (counting both MCSes and MUSes)")
    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument('--cnf', action='store_true',
                            help="assume input is in DIMACS CNF or Group CNF format (autodetected if filename is *.[g]cnf or *.[g]cnf.gz).")
    type_group.add_argument('--smt', action='store_true',
                            help="assume input is in SMT2 format (autodetected if filename is *.smt2).")
    parser.add_argument('-b', '--bias', type=str, choices=['MUSes', 'MCSes'], default='MUSes',
                        help="bias the search toward MUSes or MCSes early in the execution [default: MUSes] -- all will be enumerated eventually; this just uses heuristics to find more of one or the other early in the enumeration.")

    # Experimental / Research arguments
    exp_group = parser.add_argument_group('Experimental / research options', "These can typically be ignored; the defaults will give the best performance.")
    exp_group.add_argument('--dump-map', nargs='?', type=argparse.FileType('w'),
                           help="dump clauses added to the Map formula to the given file.")
    solver_group = exp_group.add_mutually_exclusive_group()
    solver_group.add_argument('--force-minisat', action='store_true',
                           help="use Minisat in place of MUSer2 for CNF (NOTE: much slower and usually not worth doing!)")
    solver_group.add_argument('--pmuser', type=int, default=None,
                           help="use MUSer2-para in place of MUSer2 to run in parallel (specify # of threads.)")
    exp_group.add_argument('--rnd-init', action='store_true',
                           help="initialize variable activity in csolver to random values.")

    # Max/min-models arguments
    max_group_outer = parser.add_argument_group('  Maximal/minimal models options', "By default, the Map solver will efficiently produce maximal/minimal models itself by giving each variable a default polarity.  These options override that (--nomax, -m) or extend it (-M, --smus) in various ways.")
    max_group = max_group_outer.add_mutually_exclusive_group()
    max_group.add_argument('--nomax', action='store_true',
                           help="perform no model maximization whatsoever (applies either shrink() or grow() to all seeds)")
    max_group.add_argument('-m', '--max', type=str, choices=['always', 'half'], default=None,
                           help="get a random seed from the Map solver initially, then compute a maximal/minimal model (for bias of MUSes/MCSes, resp.) for all seeds ['always'] or only when initial seed doesn't match the --bias ['half'] (i.e., seed is SAT and bias is MUSes)")
    max_group.add_argument('-M', '--MAX', action='store_true', default=None,
                           help="computes a maximum/minimum model (of largest/smallest cardinality) (uses MiniCard as Map solver)")
    max_group.add_argument('--smus', action='store_true',
                           help="calculate an SMUS (smallest MUS) (uses MiniCard as Map solver)")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    if args.smt and args.infile == sys.stdin:
        sys.stderr.write("SMT cannot be read from STDIN.  Please specify a filename.\n")
        sys.exit(1)

    return args


def at_exit(stats):
    # print stats
    times = stats.get_times()
    counts = stats.get_counts()
    other = stats.get_stats()

    # sort categories by total runtime
    categories = sorted(times, key=times.get)
    maxlen = max(len(x) for x in categories)
    for category in categories:
        sys.stderr.write("%-*s : %8.3f\n" % (maxlen, category, times[category]))
    for category in categories:
        if category in counts:
            sys.stderr.write("%-*s : %8d\n" % (maxlen + 6, category + ' count', counts[category]))
            sys.stderr.write("%-*s : %8.5f\n" % (maxlen + 6, category + ' per', times[category] / counts[category]))

    # print min, max, avg of other values recorded
    if other:
        maxlen = max(len(x) for x in other)
        for name, values in other.items():
            sys.stderr.write("%-*s : %f\n" % (maxlen + 4, name + ' min', min(values)))
            sys.stderr.write("%-*s : %f\n" % (maxlen + 4, name + ' max', max(values)))
            sys.stderr.write("%-*s : %f\n" % (maxlen + 4, name + ' avg', sum(values) / float(len(values))))


def error_exit(error, details, exception):
    sys.stderr.write("[31;1mERROR:[m %s\n[33m%s[m\n\n" % (error, details))
    sys.stderr.write(str(exception) + "\n")
    sys.exit(1)


def setup_execution(args, stats):
    # register timeout/interrupt handler
    def handler(signum, frame):  # pylint: disable=unused-argument
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
        atexit.register(at_exit, stats)


def setup_solvers(args):
    infile = args.infile

    # create appropriate constraint solver
    if args.cnf or infile.name.endswith('.cnf') or infile.name.endswith('.cnf.gz') or infile.name.endswith('.gcnf') or infile.name.endswith('.gcnf.gz'):
        if args.force_minisat:
            solverclass = CNFsolvers.MinisatSubsetSolver
        else:
            solverclass = CNFsolvers.MUSerSubsetSolver

        try:
            if args.pmuser is not None:
                csolver = solverclass(infile, args.rnd_init, numthreads=args.pmuser)
            else:
                csolver = solverclass(infile, args.rnd_init)
        except CNFsolvers.MUSerException as e:
            error_exit("Unable to use MUSer2 for MUS extraction.", "Use --force-minisat to use Minisat instead (NOTE: it will be much slower.)", e)
        except (IOError, OSError) as e:
            error_exit("Unable to load pyminisolvers library.", "Run 'make -C pyminisolvers' to compile the library.", e)
        infile.close()
    elif args.smt or infile.name.endswith('.smt2'):
        try:
            from SMTsolvers import Z3SubsetSolver
        except ImportError as e:
            error_exit("Unable to import z3 module.", "Please install Z3 from https://github.com/Z3Prover/z3", e)
        # z3 has to be given a filename, not a file object, so close infile and just pass its name
        infile.close()
        csolver = Z3SubsetSolver(infile.name)
    else:
        sys.stderr.write(
            "Cannot determine filetype (cnf or smt) of input: %s\n"
            "Please provide --cnf or --smt option.\n" % infile.name
        )
        sys.exit(1)

    # create appropriate map solver
    if args.nomax or args.max:
        varbias = None  # will get a "random" seed from the Map solver
    else:
        varbias = (args.bias == 'MUSes')  # High bias (True) for MUSes, low (False) for MCSes

    try:
        if args.MAX or args.smus:
            msolver = mapsolvers.MinicardMapSolver(n=csolver.n, bias=varbias)
        else:
            msolver = mapsolvers.MinisatMapSolver(n=csolver.n, bias=varbias, dump=args.dump_map)
    except OSError as e:
        error_exit("Unable to load pyminisolvers library.", "Run 'make -C pyminisolvers' to compile the library.", e)

    return (csolver, msolver)


def setup_config(args):
    config = {}
    config['bias'] = args.bias
    config['smus'] = args.smus
    if args.nomax:
        config['maximize'] = 'none'
    elif args.smus:
        config['maximize'] = 'always'
    elif args.max:
        config['maximize'] = args.max
    elif args.MAX:
        config['maximize'] = 'solver'
    else:
        config['maximize'] = 'solver'
    config['verbose'] = args.verbose > 1

    return config


def main():
    stats = utils.Statistics()

    with stats.time('setup'):
        args = parse_args()
        setup_execution(args, stats)
        csolver, msolver = setup_solvers(args)
        config = setup_config(args)
        mp = MarcoPolo(csolver, msolver, stats, config)

    # useful for timing just the parsing / setup
    if args.limit == 0:
        sys.stderr.write("Result limit reached.\n")
        sys.exit(0)

    # enumerate results in a separate thread so signal handling works while in C code
    # ref: https://thisismiller.github.io/blog/CPython-Signal-Handling/
    def do_enumerate():
        remaining = args.limit

        for result in mp.enumerate():
            output = result[0]
            if args.alltimes:
                output = "%s %0.3f" % (output, stats.total_time())
            if args.verbose:
                output = "%s %s" % (output, " ".join([str(x) for x in result[1]]))

            print(output)

            if remaining:
                remaining -= 1
                if remaining == 0:
                    sys.stderr.write("Result limit reached.\n")
                    sys.exit(0)

    enumthread = threading.Thread(target=do_enumerate)
    enumthread.daemon = True       # so thread is killed when main thread exits (e.g. in signal handler)
    enumthread.start()
    if sys.version_info[0] >= 3:
        enumthread.join()
    else:
        # In Python 2, a timeout is required for join() to not just
        # call a blocking C function (thus blocking the signal handler).
        # However, infinity works.
        enumthread.join(float("inf"))


if __name__ == '__main__':
    main()
