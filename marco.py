#!/usr/bin/env python

import argparse
import atexit
import copy
import multiprocessing
import os
import select
import signal
import sys
import threading

import utils
import mapsolvers
import CNFsolvers
from MCSEnumerator import MCSEnumerator
from MarcoPolo import MarcoPolo


def parse_args():
    parser = argparse.ArgumentParser()

    # Standard arguments
    parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'),
                        default=sys.stdin,
                        help="name of file to process (STDIN if omitted, in which case use --cnf or --smt)")
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
    parser.add_argument('--print-mcses', action='store_true',
                        help="for every satisfiable subset found, print the constraints in its complementary MCS instead of the MSS.")
    parser.add_argument('--check-muser', action='store_true',
                        help="just run a check of the MUSer2 helper application and exit (used to configure tests).")

    # Parallelization arguments
    par_group = parser.add_argument_group('Parallelization options', "Enable and configure parallel MARCOs execution.")
    par_group.add_argument('--parallel', type=str, default=None,
                           help="run MARCO in parallel, specifying a comma-delimited list of modes selected from: 'MUS', 'MCS', 'MCSonly' -- e.g., \"MUS,MUS,MCS,MCSonly\" will run four separate threads: two MUS biased, one MCS biased, and one with a CAMUS-style MCS enumerator.")
    par_group.add_argument('--same-seeds', action='store_true',
                           help="use same seeds for all children (still randomized but with all seeds of value 1.")
    par_group.add_argument('--all-randomized', action='store_true',
                           help="randomly initialize *all* children in parallel mode (default: first thread is *not* randomly initialized, all others are).")
    comms_group = par_group.add_mutually_exclusive_group()
    comms_group.add_argument('--comms-disable', action='store_true',
                             help="disable the communications between children (i.e., when the master receives a result from a child, it won't send to other children).")
    comms_group.add_argument('--comms-ignore', action='store_true',
                             help="send results out to children, but do not *use* the results in children (i.e., do not add blocking clauses based on them) -- used only for determining cost of communication.")

    # Experimental / Research arguments
    exp_group = parser.add_argument_group('Experimental / research options', "These can typically be ignored; the defaults will give the best performance.")
    exp_group.add_argument('--mcs-only', action='store_true', default=False,
                           help="enumerate MCSes only using a CAMUS-style MCS enumerator.")
    exp_group.add_argument('--rnd-init', type=int, nargs='?', const=1, default=None,   # default = val if --rnd-init not specified; const = val if --rnd-init specified w/o a value
                           help="only used if *not* using --parallel: initialize variable activity in solvers to random values (optionally specify a random seed [default: 1 if --rnd-init specified without a seed]).")
    exp_group.add_argument('--improved-implies', action='store_true',
                           help="use improved technique for Map formula implications (implications under assumptions) [default: False, use only singleton MCSes as hard constraints]")
    exp_group.add_argument('--dump-map', nargs='?', type=argparse.FileType('w'),
                           help="dump clauses added to the Map formula to the given file.")
    solver_group = exp_group.add_mutually_exclusive_group()
    solver_group.add_argument('--force-minisat', action='store_true',
                              help="use Minisat in place of MUSer2 for CNF (NOTE: much slower and usually not worth doing!)")
    solver_group.add_argument('--pmuser', type=int, default=None,
                              help="use MUSer2-para in place of MUSer2 to run in parallel (specify # of threads.)")
    exp_group.add_argument('--nomax', action='store_true',
                           help="perform no model maximization whatsoever (applies either shrink() or grow() to all seeds)")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    if args.check_muser:
        try:
            muser_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'muser2-para')
            utils.check_executable("MUSer2", muser_path)
        except utils.ExecutableException as e:
            print(str(e))
            sys.exit(1)
        sys.exit(0)

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
    for category in sorted(counts):
        sys.stderr.write("%-*s : %8d\n" % (maxlen + 6, category + ' count', counts[category]))
        if category in times:
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


def setup_execution(args, stats, mainpid):
    # register timeout/interrupt handler

    def handler(signum, frame):  # pylint: disable=unused-argument
        # only report out and propagate to process group if we're the main process
        mypid = os.getpid()
        if mypid == mainpid:
            if signum == signal.SIGALRM:
                sys.stderr.write("Time limit reached.\n")
            else:
                sys.stderr.write("Interrupted.\n")

            # prevent an infinite recursion of signal handlers calling
            # themselves when we signal the process group next
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            # kill all children (all procs in process group)
            os.killpg(mainpid, signal.SIGTERM)

        sys.exit(128)
        # at_exit will fire here in the main process

    signal.signal(signal.SIGTERM, handler)  # external termination
    signal.signal(signal.SIGINT, handler)   # ctl-c keyboard interrupt

    # register a timeout alarm, if needed
    if args.timeout:
        signal.signal(signal.SIGALRM, handler)  # timeout alarm
        signal.alarm(args.timeout)

    # register at_exit to print stats when program exits
    if args.stats:
        atexit.register(at_exit, stats)


def setup_csolver(args, seed):
    infile = args.infile

    # create appropriate constraint solver
    if args.cnf or infile.name.endswith('.cnf') or infile.name.endswith('.cnf.gz') or infile.name.endswith('.gcnf') or infile.name.endswith('.gcnf.gz'):
        if args.force_minisat or args.mcs_only:  # mcs_only doesn't care about fancy features, give it a plain MinisatSubsetSolver
            solverclass = CNFsolvers.MinisatSubsetSolver
        elif args.improved_implies:
            solverclass = CNFsolvers.ImprovedImpliesSubsetSolver
        else:
            solverclass = CNFsolvers.MUSerSubsetSolver

        try:
            if args.mcs_only:
                csolver = solverclass(infile, seed, store_dimacs=True)
            elif args.pmuser is not None:
                csolver = solverclass(infile, seed, numthreads=args.pmuser)
            else:
                csolver = solverclass(infile, seed)
        except utils.ExecutableException as e:
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

    return csolver


def setup_msolver(n, args, seed=None):
    # create appropriate map solver
    if args.nomax:
        varbias = None  # will get a "random" seed from the Map solver
    else:
        varbias = (args.bias == 'MUSes')  # High bias (True) for MUSes, low (False) for MCSes

    try:
        msolverclass = mapsolvers.MinisatMapSolver
        if args.parallel:
            # Synchronize if running in parallel mode
            msolverclass = utils.synchronize_class(msolverclass)
        msolver = msolverclass(n, bias=varbias, rand_seed=seed, dump=args.dump_map)
    except OSError as e:
        error_exit("Unable to load pyminisolvers library.", "Run 'make -C pyminisolvers' to compile the library.", e)

    return msolver


def setup_solvers(args, seed=None):
    csolver = setup_csolver(args, seed)
    msolver = setup_msolver(csolver.n, args, seed)

    try:
        csolver.set_msolver(msolver)
    except AttributeError:
        pass

    return (csolver, msolver)


def setup_config(args):
    config = {}
    config['bias'] = args.bias
    config['comms_ignore'] = args.comms_ignore
    if args.nomax:
        config['maximize'] = False
    else:
        config['maximize'] = True
    config['verbose'] = args.verbose > 1

    return config


def run_enumerator(stats, args, seed=None, pipe=None):
    csolver, msolver = setup_solvers(args, seed)
    config = setup_config(args)

    if args.mcs_only:
        enumerator = MCSEnumerator(csolver, stats, config, pipe)
    else:
        enumerator = MarcoPolo(csolver, msolver, stats, config, pipe)

    # enumerate results in a separate thread so signal handling works while in C code
    # ref: https://thisismiller.github.io/blog/CPython-Signal-Handling/
    def enumerate():
        remaining = args.limit
        for result in enumerator.enumerate():
            if pipe:
                pipe.send(result)
            else:
                print_result(result, args, stats, csolver.n)
                if remaining:
                    remaining -= 1
                    if remaining == 0:
                        sys.stderr.write("Result limit reached.\n")
                        return

    enumthread = threading.Thread(target=enumerate)
    enumthread.daemon = True  # required so signal handler exit will end enumeration thread
    enumthread.start()
    if sys.version_info[0] >= 3:
        enumthread.join()
    else:
        # In Python 2, a timeout is required for join() to not just
        # call a blocking C function (thus blocking the signal handler).
        # However, infinity works.
        enumthread.join(float('inf'))


def run_master(stats, args, pipes):
    # for filtering duplicate results (found near-simultaneously by 2+ children)
    # and spurious results (if using improved-implies and a child reaches a point that
    # suddenly becomes blocked by new blocking clauses, it could return that incorrectly
    # as an MUS or MCS)
    # Need to parse the constraint set (again!) just to get n for the map formula...
    csolver = setup_csolver(args, seed=None)
    msolver = mapsolvers.MinisatMapSolver(csolver.n)
    # Old way: results = set()

    remaining = args.limit

    while multiprocessing.active_children() and pipes:
        ready, _, _ = select.select(pipes, [], [])
        with stats.time('hubcomms'):
            for receiver in ready:
                while receiver.poll():
                    try:
                        # get a result
                        result = receiver.recv()
                    except EOFError:
                        # Sometimes a closed pipe will still trigger ready and .poll(),
                        # but it then throws an EOFError on .recv().  Handle that here.
                        pipes.remove(receiver)
                        break

                    if result[0] == 'done':
                        # "done" indicates the child process has finished its work,
                        # but enumeration may not be complete (if the child was only
                        # enumerating MCSes, e.g.)
                        if args.verbose > 1:
                            print("Child (%s) sent 'done'." % receiver)
                        # Terminate the child process.
                        receiver.send('terminate')
                        # Remove it from the list of active pipes
                        pipes.remove(receiver)

                    elif result[0] == 'complete':
                        # "complete" indicates the child process has completed enumeration,
                        # with everything blocked.  Everything can be stopped at this point.
                        if args.verbose > 1:
                            print("Child (%s) sent 'complete'." % receiver)

                        # TODO: print children's results, but differentiate somehow...
                        #if args.stats:
                        #    # Print received stats
                        #    at_exit(result[1])

                        # End / cleanup all children
                        for pipe in pipes:
                            pipe.send('terminate')
                        # Exit main process
                        sys.exit(0)

                    else:
                        assert result[0] in ['U', 'S']
                        # filter out duplicate / spurious results
                        with stats.time('msolver'):
                            if not msolver.check_seed(result[1]):
                                if args.verbose > 1:
                                    print("Child (%s) sent duplicate (len: %d)" % (receiver, len(result[1])))
                                if result[0] == 'U':
                                    stats.increment_counter("duplicate MUS")
                                else:
                                    stats.increment_counter("duplicate MSS")

                                # already found/reported/explored
                                continue

                        with stats.time('msolver_block'):
                            if result[0] == 'U':
                                msolver.block_up(result[1])
                            elif result[0] == 'S':
                                msolver.block_down(result[1])

                        # Old way to check duplicates:
                        #res_set = frozenset(result[1])
                        #res_set = ",".join(str(x) for x in result[1])
                        #if res_set in results:
                        #    continue

                        #results.add(res_set)

                        print_result(result, args, stats, csolver.n)

                        if remaining:
                            remaining -= 1
                            if remaining == 0:
                                sys.stderr.write("Result limit reached.\n")
                                # End / cleanup all children
                                for pipe in pipes:
                                    pipe.send('terminate')
                                # Exit main process
                                sys.exit(0)

                        if not args.comms_disable:
                            # send it to all children *other* than the one we got it from
                            for other in pipes:
                                if other != receiver:
                                    other.send(result)


def print_result(result, args, stats, num_constraints):
    if result[0] == 'S' and args.print_mcses:
        # MCS = the complement of the MSS relative to the full set of constraints
        result = ('C', set(range(1, num_constraints+1)).difference(result[1]))
    output = result[0]
    if args.alltimes:
        output = "%s %0.3f" % (output, stats.total_time())
    if args.verbose:
        output = "%s %s" % (output, " ".join([str(x) for x in result[1]]))

    print(output)


def main():
    stats = utils.Statistics()

    pipes = []
    procs = []

    # make process group id match process id so all children
    # will share the same group id (for easier termination)
    os.setpgrp()

    with stats.time('setup'):
        args = parse_args()
        setup_execution(args, stats, os.getpid())
        if args.same_seeds or args.comms_disable:
            assert args.parallel is not None, "some flags you have specified have to be tested in the parallel mode."

        if args.parallel:
            for i, mode in enumerate(args.parallel.split(',')):
                newargs = copy.copy(args)
                if mode == 'MUS':
                    newargs.bias = 'MUSes'
                elif mode == 'MCS':
                    newargs.bias = 'MCSes'
                elif mode == 'MCSonly':
                    newargs.mcs_only = True
                else:
                    assert False, "Invalid parallel mode: %s" % mode

                pipe, child_pipe = multiprocessing.Pipe()
                pipes.append(pipe)

                if args.same_seeds:
                    if args.all_randomized:
                        seed = 1
                    else:
                        seed = None
                else:
                    # TODO: Handle randomization with non-homogeneous thread modes
                    if not args.all_randomized and i == 0:
                        seed = None
                    else:
                        seed = i+1

                proc = multiprocessing.Process(target=run_enumerator, args=(stats, newargs, seed, child_pipe))
                procs.append(proc)

    # useful for timing just the parsing / setup
    if args.limit == 0:
        sys.stderr.write("Result limit reached.\n")
        sys.exit(0)

    if args.parallel:
        for proc in procs:
            proc.start()
        run_master(stats, args, pipes)

    else:
        run_enumerator(stats, args, seed=args.rnd_init)


if __name__ == '__main__':
    main()
