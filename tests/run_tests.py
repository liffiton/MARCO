#!/usr/bin/env python3
#
# run_tests.py -- Run regression tests
#
# Author: Mark Liffiton
# Date: October 2012
#

import json
import math
import os
import re
import sys
import subprocess
import tempfile
import time
from collections import defaultdict
from queue import Empty
from multiprocessing import Process, Queue, cpu_count

# pull in configuration from testconfig.py
import testconfig

# globals (w/ default values)
mode = 'runp'
verbose = False


# Build all tests to be run
def makeTests(testname):
    tests = []

    for job in testconfig.jobs:
        if testname is None:
            if job['default'] is False:
                continue
        else:
            if testname != 'all' and job['name'] != testname:
                continue

        name = job['name']
        files = job['files']
        flags = job.get('flags', [''])
        flags_all = job.get('flags_all', [])
        exclude = job.get('exclude', [])
        out_filter = job.get('out_filter', None)

        outdir = "out/" + name + "/"
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        for flag in flags:
            cmdarray = testconfig.cmd_array + flags_all.split() + flag.split()

            for infile in files:
                if infile in exclude:
                    continue

                if not os.path.exists(outdir + os.path.dirname(infile)):
                    os.makedirs(outdir + os.path.dirname(infile))

                outfile = outdir + infile + ".out"
                errfile = outdir + infile + ".err"

                tests.append( {'cmdarray': cmdarray + [infile], 'outfile': outfile, 'errfile': errfile, 'out_filter': out_filter } )

    return tests


def runTests(jobq, msgq, pid):
    while True:
        try:
            # Block with a small timeout, because the non-blocking get_nowait()
            # sometimes thinks the Queue is empty when it's not...
            job = jobq.get(True, 0.1)
        except Empty:
            break
        msgq.put((job['id'], 'start', None))
        result, runtime = runTest(job['cmdarray'], job['outfile'], job['errfile'], pid, job['out_filter'])
        if result == 'interrupted':
            msgq.put((None, 'done', None))
            return
        msgq.put((job['id'], result, runtime))
    msgq.put((None, 'done', None))


# pid is so different processes don't overwrite each other's tmp files
def runTest(cmd, outfile, errfile, pid, out_filter=None):
    global mode, verbose

    if mode == "nocheck":
        tmpout = os.devnull
        tmperr = os.devnull
    elif mode == "regenerate":
        tmpout = outfile
        tmperr = os.devnull
    else:
        tmpout = outfile + ".NEW" + str(pid)
        tmperr = errfile + str(pid)
        if not os.path.exists(outfile):
            if verbose:
                print("\n[33mKnown-good output does not exist:[0m %s\nPlease run in '[34;1mregenerate[0m' mode first." % outfile)
            return 'missing output', None

    if verbose:
        print("\n[34;1mRunning test:[0m %s > %s 2> %s" % (" ".join(cmd), tmpout, tmperr))

    with open(tmpout, 'w') as f_out, open(tmperr, 'w') as f_err:
        try:
            start_time = time.time()  # time() for wall-clock time
            ret = subprocess.call(cmd, stdout=f_out, stderr=f_err)
            runtime = time.time() - start_time
        except KeyboardInterrupt:
            os.remove(tmpout)
            os.remove(tmperr)
            return 'interrupted', None

    if ret > 128:
        return 'fail', None

    if mode == "nocheck" or mode == "regenerate":
        return 'pass', runtime

    result = checkFiles(outfile, tmpout, out_filter)
    if result != 'pass' and result != 'sortsame':
        # don't report/store a runtime for failures
        runtime = None

    if verbose:
        if result == 'pass':
            errsize = os.path.getsize(tmperr)
            if errsize:
                print("  [32mTest passed (with output to stderr).[0m")
                result = 'stderr'
            else:
                print("  [32mTest passed.[0m")
        elif result == 'sortsame':
            print("  [33mOutputs not equivalent, but sort to same contents.[0m")
        else:
            print("\n  [37;41mTest failed:[0m %s" % " ".join(cmd))
            errsize = os.path.getsize(tmperr)
            if errsize:
                print("  [31mStderr output:[0m")
                with open(tmperr, 'r') as f:
                    for line in f:
                        print("    " + line.rstrip())
            viewdiff(outfile, tmpout)
            updateout(outfile, tmpout)

    try:
        os.remove(tmpout)
        os.remove(tmperr)
    except OSError:
        pass
    return result, runtime


def checkFiles(file1, file2, out_filter=None):
    global verbose

    with open(file1) as f1:
        data1 = f1.read()
        if out_filter is not None:
            data1 = re.sub("^.*%s.*\n" % out_filter, '', data1, flags=re.MULTILINE)
    with open(file2) as f2:
        data2 = f2.read()
        if out_filter is not None:
            data2 = re.sub("^.*%s.*\n" % out_filter, '', data2, flags=re.MULTILINE)

    if len(data1) != len(data2):
        if verbose:
            print("\n  [31mOutputs differ (size).[0m")
        return 'diffsize'

    if data1 != data2:
        # test sorted lines
        sort1 = data1.split('\n').sort()
        sort2 = data2.split('\n').sort()
        if sort1 != sort2:
            if verbose:
                print("\n  [31mOutputs differ (contents).[0m")
            return 'diffcontent'
        else:
            # outputs not equivalent, but sort to same contents
            return 'sortsame'

    # everything checks out
    return 'pass'


# TODO: read single keypress, like "read -n 1" in old bash script, for viewdiff and updateout
#       http://stackoverflow.com/questions/510357/
def viewdiff(f1, f2):
    choice = input("  View diff? (T for terminal, V for vimdiff, S for sorted vimdiff, other for no) ")
    if choice.lower() == 'v':
        subprocess.call(["vimdiff", f1, f2])
    elif choice.lower() == 't':
        subprocess.call(["diff", f1, f2])
    elif choice.lower() == 's':
        with tempfile.NamedTemporaryFile('wb') as tmp1, tempfile.NamedTemporaryFile('wb') as tmp2:
            subprocess.call(["sort", f1], stdout=tmp1)
            subprocess.call(["sort", f2], stdout=tmp2)
            subprocess.call(["vimdiff", tmp1.name, tmp2.name])


def updateout(outfile, newoutput):
    choice = input("  Store new output as correct? (y/N) ")
    if choice.lower() == 'y':
        print("  [33mmv %s %s[0m" % (newoutput, outfile))
        os.rename(newoutput, outfile)


class Progress:
    # indicator characters
    chr_Pass = "[32m*[0m"
    chr_Sort = "[33m^[0m"
    chr_StdErr = "[34mo[0m"
    chr_Fail = "[37;41mx[0m"

    def __init__(self, numTests, do_print):
        # maintain test stats
        self.stats = {
            'total': numTests,
            'passed': 0,
            'sortsame': 0,
            'stderr': 0,
            'fail': 0,
            'incomplete': numTests,
        }

        self.do_print = do_print

        if self.do_print:
            # get size of terminal (thanks: stackoverflow.com/questions/566746/)
            self.rows, self.cols = os.popen('stty size', 'r').read().split()
            self.cols = int(self.cols)

            # figure size of printed area
            self.printrows = int(math.ceil(float(numTests) / (self.cols-2)))

            # move forward for blank lines to hold progress bars
            for i in range(self.printrows + 1):
                print('')
            # print '.' for every test to be run
            for i in range(numTests):
                x = i % (self.cols-2) + 2
                y = i // (self.cols-2)
                self.print_at(x, self.printrows-y, '.')

    def update(self, testid, result):
        # print correct mark, update stats
        if result == 'start':
            c = ':'
        elif result == 'pass' or result == 'sortsame' and not verbose:
            c = self.chr_Pass
            self.stats['passed'] += 1
            self.stats['incomplete'] -= 1
        elif result == 'sortsame':
            c = self.chr_Sort
            self.stats['passed'] += 1
            self.stats['sortsame'] += 1
            self.stats['incomplete'] -= 1
        elif result == 'stderr':
            c = self.chr_StdErr
            self.stats['stderr'] += 1
            self.stats['incomplete'] -= 1
        else:
            c = self.chr_Fail
            self.stats['fail'] += 1
            self.stats['incomplete'] -= 1

        if self.do_print:
            x = testid % (self.cols-2) + 2
            y = testid // (self.cols-2)
            self.print_at(x, self.printrows-y, c)

    def printstats(self):
        print('')
        if self.stats['incomplete'] > 0:
            # red text
            sys.stdout.write("[31m")
            print("     %3d / %d  Incomplete" %
                  (self.stats['incomplete'], self.stats['total']))
            sys.stdout.write("[0m")
        print(" %s : %3d / %d  Passed" %
              (self.chr_Pass, self.stats['passed'], self.stats['total']))
        if self.stats['sortsame'] > 0:
            print(" %s : %3d   Different order, same contents" %
                  (self.chr_Sort, self.stats['sortsame']))
        if self.stats['stderr'] > 0:
            print(" %s : %3d   Produced output to STDERR" %
                  (self.chr_StdErr, self.stats['stderr']))
        if self.stats['fail'] > 0:
            print(" %s : %3d   Failed" %
                  (self.chr_Fail, self.stats['fail']))
            if self.do_print:
                print("     Re-run in 'runverbose' mode to see failure details.")

    # x is 1-based
    # y is 0-based, with 0 = lowest row, 1 above that, etc.
    def print_at(self, x, y, string):
        # move to correct position
        sys.stdout.write("[%dF" % y)  # y (moves to start of row)
        sys.stdout.write("[%dG" % x)         # x

        sys.stdout.write(string)

        # move back down
        sys.stdout.write("[%dE" % y)

        # move cursor to side and flush anything pending
        sys.stdout.write("[0G")
        sys.stdout.flush()


class TimeData:
    def __init__(self, filename="runtimes.json"):
        self.filename = filename
        try:
            with open(self.filename, 'r') as f:
                data = f.read()
            self.times = defaultdict(int, json.loads(data))
            self.have_times = True
        except:
            #print "No timing data found.  Timing data will be regenerated."
            self.times = defaultdict(int)
            self.have_times = False

    def sort_by_time(self, jobs):
        return sorted(jobs, key=lambda x: self.times[" ".join(x['cmdarray'])])

    def get_time(self, cmdarray):
        return self.times[" ".join(cmdarray)]

    def store_time(self, cmdarray, runtime):
        self.times[" ".join(cmdarray)] = runtime

    def save_data(self):
        with open(self.filename, 'w') as f:
            f.write(json.dumps(self.times))


def main():
    global mode, verbose

    if len(sys.argv) >= 2:
        mode = sys.argv[1]

    if len(sys.argv) >= 3:
        testname = sys.argv[2]
    else:
        testname = None

    td = TimeData()

    validmodes = ('run', 'runp', 'runverbose', 'nocheck', 'regenerate')

    if mode not in validmodes:
        print("Invalid mode: %s" % mode)
        print("Options: %s" % ", ".join(validmodes))
        return 1

    if mode == 'runverbose':
        verbose = True
        mode = 'run'
    elif mode == 'regenerate':
        sure = input("Are you sure you want to regenerate all test outputs? (y/N) ")
        if sure.lower() != 'y':
            print("Exiting.")
            return 1

    if mode == "runp":
        # run tests in parallel
        num_procs = cpu_count()
    else:
        # run, nocheck, and regenerate are done serially.
        #  (nocheck is best for timing, and regenerate
        #  can have issues with output file clashes.)
        num_procs = 1

    # build the tests
    jobs = makeTests(testname)
    numTests = len(jobs)
    # sort by times, if we have them
    jobs = td.sort_by_time(jobs)
    # give each an increasing 'id'
    for idx, job in enumerate(jobs):
        job['id'] = idx

    # say what we are about to do
    if testname is None:
        testname = "default"
    else:
        testname = "'%s'" % testname
    report = "Running %d %s tests on %d cores" % (numTests, testname, num_procs)
    if mode == 'nocheck':
        report += " (skipping results checks)"
    if mode == 'regenerate':
        report += " (to regenerate output files)"
    if td.have_times:
        report += " (sorted by previously recorded runtimes)"
    report += "."
    print(report)

    # run the tests
    jobq = Queue()  # jobs *to* each process
    for job in jobs:
        jobq.put(job)
    msgq = Queue()  # messages *from* each process

    # wait for completion, printing progress/stats as needed
    # if verbose is on, printing the progress bar is not needed/wanted
    prog = Progress(numTests, do_print=(not verbose))

    try:
        if verbose:
            # run in same process so viewdiff, etc. can get stdin
            runTests(jobq, msgq, 1)
        else:
            for pid in range(num_procs):
                p = Process(target=runTests, args=(jobq, msgq, pid,))
                p.daemon = True
                p.start()

        procs_done = 0
        while procs_done < num_procs:
            testid, result, runtime = msgq.get()
            if result == 'done':
                procs_done += 1
            else:
                if runtime:
                    td.store_time(jobs[testid]['cmdarray'], runtime)
                prog.update(testid, result)

    except KeyboardInterrupt:
        print('')
        print("[31;1mInterrupted![0m")

    if mode == "run" or mode == "runp":
        prog.printstats()

    # save any time data to disk
    td.save_data()


if __name__ == '__main__':
    main()
