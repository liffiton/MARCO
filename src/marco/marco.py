import argparse
import atexit
import copy
import multiprocessing
import os
import select
import signal
import sys
import threading

from . import utils
from . import mapsolvers
from . import CNFsolvers
from .MCSEnumerator import MCSEnumerator
from .MarcoPolo import MarcoPolo


def default_parallel_config(threads=None, bias=None):
    ''' Get a default parallel configuration for this system.

    If threads is specified, that is used.  Otherwise, it defaults to 1 thread
    per 2 cores (basically assuming each physical core has two logical cores,
    and we only want to run one thread per physical core).

    If bias is specified, it is used for all threads.  Otherwise, threads will
    be MUS biased, with one MCS biased only if the thread count is 4 or higher.
    '''
    if threads is None:
        num_procs = multiprocessing.cpu_count()
        threads = max(1, num_procs // 2)

    if bias is not None:
        bias = bias.replace('es', '')
        types = [bias] * (threads)
    elif threads > 3:
        types = ['MUS'] * (threads - 1) + ['MCS']
    else:
        types = ['MUS'] * (threads)
    return ','.join(types)


def parse_args(args_list=None):
    '''Parse a list of arguments and return the resulting configuration.

    Parameters:
        args_list (list of strings): by default (when None), this function will
            take arguments from sys.argv (the command line).  This can
            optionally be specified as a list of argument strings like:
                ['--parallel','MUS,MUS,MUS,MUS','file1.cnf']

    Returns:
        An argparse.NameSpace object containing all configured options,
        each accessible via dot notation.  (E.g., args.verbose)
    '''

    parser = argparse.ArgumentParser()

    # Required arguments
    required_args = parser.add_mutually_exclusive_group(required=True)
    # we don't use the file object, but using that type verifies that it exists as a file
    required_args.add_argument('inputfile', nargs='?', type=argparse.FileType('rb'),
                               help="name of file to process")
    required_args.add_argument('--check-muser', action='store_true',
                               help="just run a check of the MUSer2 helper application and exit (used to configure tests).")

    # Standard arguments
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
    parser.add_argument('--print-mcses', action='store_true',
                        help="for every satisfiable subset found, print the constraints in its complementary MCS instead of the MSS.")

    # Parallelization arguments
    par_group = parser.add_argument_group('Parallelization options', "Configure parallel MARCOs execution.  By default, it will run in parallel in a configuration that should work well on most systems, using #CPUs/2 threads and a mix of MUS and MCS bias.  On *this* system, that default is equivalent to --parallel %s.  You can override that default and control the parallelization using the following options." % default_parallel_config())

    par_types_group = par_group.add_mutually_exclusive_group()
    par_types_group.add_argument('--threads', type=int, default=None,
                                 help="override how many threads to use, but use the default thread types.")
    par_types_group.add_argument('-b', '--bias', type=str, choices=['MUSes', 'MCSes'], default=None,
                                  help="override the bias for all threads (toward MUSes or MCSes), but use the default number of threads.")
    par_types_group.add_argument('--parallel', type=str, default=None,
                                 help="specify the exact number of threads and mode for each as a comma-delimited list of modes selected from: 'MUS', 'MCS', 'MCSonly' -- e.g., \"MUS,MUS,MCS,MCSonly\" will run four separate threads: two MUS biased, one MCS biased, and one with a CAMUS-style MCS enumerator.")

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
    exp_group.add_argument('--nomax', action='store_true',
                           help="perform no model maximization whatsoever (applies either shrink() or grow() to all seeds)")
    exp_group.add_argument('--all-randomized', action='store_true',
                           help="randomly initialize *all* children in parallel mode (default: first thread is *not* randomly initialized, all others are).")
    comms_group = exp_group.add_mutually_exclusive_group()
    comms_group.add_argument('--comms-disable', action='store_true',
                             help="disable the communications between children (i.e., when the master receives a result from a child, it won't send to other children).")
    comms_group.add_argument('--comms-ignore', action='store_true',
                             help="send results out to children, but do not *use* the results in children (i.e., do not add blocking clauses based on them) -- used only for determining cost of communication.")

    # parse args_list and return resulting arguments
    args = parser.parse_args(args_list)
    # we can't use the file object directly because it can't be shared with child processes,
    # so close it immediately
    if args.inputfile:
        args.inputfile.close()

    if args.parallel is None:
        args.parallel = default_parallel_config(args.threads, args.bias)

    return args


def check_args(args):
    if args.check_muser:
        try:
            muser_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'muser2-para')
            utils.check_executable("MUSer2", muser_path)
        except utils.ExecutableException as e:
            print(str(e))
            sys.exit(1)
        sys.exit(0)

    if not (args.smt or args.cnf or args.inputfile.name.endswith(('.cnf', '.cnf.gz', '.gcnf', '.gcnf.gz', '.smt2'))):
        error_exit(
            "Cannot determine filetype (cnf or smt) of input: %s" % args.inputfile.name,
            "Please provide --cnf or --smt option, or --help to see all options."
        )


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


def error_exit(error, details=None, exception=None):
    sys.stderr.write("[31;1mERROR:[m %s\n" % error)
    if details is not None:
        sys.stderr.write("[33m%s[m\n" % details)
    if exception is not None:
        sys.stderr.write("\n%s\n" % str(exception))
    sys.exit(1)


def setup_execution(args, stats, mainpid):
    # make process group id match process id so all children
    # will share the same group id (for easier termination)
    os.setpgrp()

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


def setup_parallel(args, stats):

    argslist = []

    if args.parallel:
        for mode in args.parallel.split(','):
            newargs = copy.copy(args)
            if mode == 'MUS':
                newargs.bias = 'MUSes'
            elif mode == 'MCS':
                newargs.bias = 'MCSes'
            elif mode == 'MCSonly':
                newargs.mcs_only = True
            else:
                error_exit("Invalid parallel mode: %s" % mode)
            argslist.append(newargs)
    else:
        argslist.append(args)

    pipes = []
    procs = []

    for i, args in enumerate(argslist):
        pipe, child_pipe = multiprocessing.Pipe()
        pipes.append(pipe)

        # TODO: Handle randomization with non-homogeneous thread modes
        if not args.all_randomized and i == 0:
            # don't randomize the first thread in this case
            seed = None
        else:
            seed = i+1

        proc = multiprocessing.Process(target=run_enumerator, args=(stats, args, child_pipe, seed))
        procs.append(proc)

    return pipes, procs


def setup_csolver(args, seed, n_only=False):
    filename = args.inputfile.name

    # create appropriate constraint solver
    if args.cnf or filename.endswith(('.cnf', '.cnf.gz', '.gcnf', '.gcnf.gz')):
        if args.force_minisat or args.mcs_only:  # mcs_only doesn't care about fancy features, give it a plain MinisatSubsetSolver
            solverclass = CNFsolvers.MinisatSubsetSolver
        elif args.improved_implies:
            solverclass = CNFsolvers.ImprovedImpliesSubsetSolver
        else:
            solverclass = CNFsolvers.MUSerSubsetSolver

        try:
            extra_args = {}
            if args.mcs_only:
                extra_args['store_dimacs'] = True
            csolver = solverclass(filename, seed, n_only, **extra_args)
        except utils.ExecutableException as e:
            error_exit("Unable to use MUSer2 for MUS extraction.", "Use --force-minisat to use Minisat instead (NOTE: it will be much slower.)", e)
        except (IOError, OSError) as e:
            error_exit("Unable to load pyminisolvers library.", "Run 'make -C src/pyminisolvers' to compile the library.", e)

    elif args.smt or filename.endswith('.smt2'):
        try:
            from .SMTsolvers import Z3SubsetSolver
        except ImportError as e:
            error_exit("Unable to import z3 module.", "Please install Z3 for Python:  pip install z3-solver", e)
        csolver = Z3SubsetSolver(filename)

    else:
        assert False  # this should be covered in check_args()

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
        error_exit("Unable to load pyminisolvers library.", "Run 'make -C src/pyminisolvers' to compile the library.", e)

    return msolver


def setup_solvers(args, seed=None):
    csolver = setup_csolver(args, seed)
    msolver = setup_msolver(csolver.n, args, seed)

    try:
        csolver.set_msolver(msolver)
    except AttributeError:
        pass

    return (csolver, msolver)


def get_config(args):
    config = {}
    config['bias'] = args.bias
    config['comms_ignore'] = args.comms_ignore
    if args.nomax:
        config['maximize'] = False
    else:
        config['maximize'] = True
    config['verbose'] = args.verbose > 1

    return config


def run_enumerator(stats, args, pipe, seed=None):
    # Register interrupt handler to cleanly exit if receiving SIGTERM
    # (probably from parent process)
    def handler(signum, frame):  # pylint: disable=unused-argument
        os._exit(0)
    signal.signal(signal.SIGTERM, handler)  # external termination

    csolver, msolver = setup_solvers(args, seed)
    config = get_config(args)

    if args.mcs_only:
        enumerator = MCSEnumerator(csolver, stats, config, pipe)
    else:
        enumerator = MarcoPolo(csolver, msolver, stats, config, pipe)

    # enumerate results in a separate thread so signal handling works while in C code
    # ref: https://thisismiller.github.io/blog/CPython-Signal-Handling/
    def enumerate():
        for result in enumerator.enumerate():
            pipe.send(result)

    enumthread = threading.Thread(target=enumerate)
    enumthread.daemon = True  # required so signal handler exit will end enumeration thread
    enumthread.start()
    enumthread.join()


def run_master(stats, args, pipes):
    csolver = setup_csolver(args, seed=None, n_only=True)  # just parse enough to get n (#constraints)
    is_parallel = len(pipes) > 1

    if is_parallel:
        # for filtering duplicate results (found near-simultaneously by 2+ children)
        # and spurious results (if using improved-implies and a child reaches a point that
        # suddenly becomes blocked by new blocking clauses, it could return that incorrectly
        # as an MUS or MCS)
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

                        return

                    else:
                        assert result[0] in ['U', 'S']

                        if is_parallel:
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
                            #
                            #results.add(res_set)

                        yield result, csolver.n

                        if remaining:
                            remaining -= 1
                            if remaining == 0:
                                sys.stderr.write("Result limit reached.\n")
                                # End / cleanup all children
                                for pipe in pipes:
                                    pipe.send('terminate')

                                return

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

    return output


def enumerate_with_args(args, print_results=False):
    '''Enumerate (yield) results, controlled by a set of arguments.

    Parameters:
        args (Namespace): Arguments (configuration) as produced by parse_args().
        print_results (bool): If False (the default), yield results as tuples.
                              If True, yield results as printable strings.

    This is a generator function that will yield individual results one
    at a time.  It is suitable for use in a for loop or anywhere else an
    iterator can be used.  If the generator is saved in a variable (for
    example: `gen = enumerate_with_args(args)`), then its .close() method
    can be called (`gen.close()`) to terminate the enumeration at any point.
    '''

    stats = utils.Statistics()

    with stats.time('setup'):
        check_args(args)
        setup_execution(args, stats, os.getpid())
        pipes, procs = setup_parallel(args, stats)

    # useful for timing just the parsing / setup
    if args.limit == 0:
        return

    for proc in procs:
        proc.start()

    for result, n in run_master(stats, args, pipes):
        try:
            if print_results:
                yield print_result(result, args, stats, n)
            else:
                yield result
        except GeneratorExit:
            # Handle a .close() call on the generator
            for proc in procs:
                proc.terminate()
            return


def main():
    args = parse_args()
    for result in enumerate_with_args(args, print_results=True):
        print(result)
