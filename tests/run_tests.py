#!/usr/bin/env python
#
# run_tests.py -- Run regression tests
#
# Author: Mark Liffiton
# Date: October 2012
#

import math
import os
import sys
import subprocess
from multiprocessing import Process, Queue, JoinableQueue, cpu_count

# pull in configuration from testconfig.py
import testconfig

# globals (w/ default values)
mode = 'runp'
testexe = ''
verbose = False

# Build all tests to be run, add to returned Queue
def makeTests():
    global testexe

    # Gather commands
    cmds = []
    for exe in testconfig.exes:
        if testexe != '' and exe['name'] != testexe:
            continue

        cmd = exe['cmd']

        if not os.access(cmd, os.X_OK):
            print "ERROR: %s is not an executable file.  Do you need to run make?" % cmd
            sys.exit(1)

        flags = exe.get('flags', [''])
        exclude = exe.get('exclude', [])

        for flag in flags:
            cmds.append([ [cmd] + flag.split() , exclude ])

    # Add individual tests to a Queue (to be returned)
    q = JoinableQueue()
    testid = 0  # unique id for each test
    for (cmd, exclude) in cmds:
        for testfile in testconfig.files:
            infile = testfile[0]

            if infile in exclude:
                continue

            if len(testfile) > 1:
                outfile = testfile[1]
            else:
                outfile = infile + ".out"

            outfile = "out/" + outfile

            q.put([ testid , cmd + [infile] , outfile ])
            testid += 1

    return q

def runTests(jobq, msgq, pid):
    while not jobq.empty():
        testid, cmd, outfile = jobq.get()
        msgq.put((testid,'start'))
        result = runTest(cmd, outfile, pid)
        msgq.put((testid,result))
        jobq.task_done()
    msgq.put('done')

# pid is so different processes don't overwrite each other's tmp files
def runTest(cmd, outfile, pid):
    global mode, verbose

    if mode == "nocheck":
        tmpout = os.devnull
    elif mode == "regenerate":
        tmpout = outfile
    else:
        tmpout = outfile + ".NEW" + str(pid)

    if verbose:
        print "\nRunning test: %s > %s" % (" ".join(cmd), tmpout)

    # TODO: handle stderr
    with open(tmpout, 'w') as tmpf:
        try:
            ret = subprocess.call(cmd, stdout = tmpf)
        except KeyboardInterrupt:
            return 'interrupted'   # not perfect, but seems to deal with CTL-C most of the time

    if ret > 128:
        return 'fail'

    if mode == "nocheck" or mode == "regenerate":
        return None

    result = checkFiles(outfile, tmpout)
    os.unlink(tmpout)
    if result == 'pass':
        if verbose:
            print "  [32mTest passed.[0m"
    elif result == 'sortsame':
        if verbose:
            print "  [33mOutputs not equivalent, but sort to same contents.[0m"
    else:
        print "\n  [37;41mTest failed:[0m %s" % " ".join(cmd)
        # TODO: viewdiff
        # TODO: updateout

    return result

def checkFiles(file1, file2):
    with open(file1) as f1:
        data1 = f1.read()
    with open(file2) as f2:
        data2 = f2.read()

    if len(data1) != len(data2):
        print "\n  [31mOutputs differ (size).[0m"
        return 'diffsize'

    if data1 != data2:
        # test sorted lines
        sort1 = data1.split('\n').sort()
        sort2 = data2.split('\n').sort()
        if sort1 != sort2:
            print "\n  [31mOutputs differ (contents).[0m"
            return 'diffcontent'
        else:
            # outputs not equivalent, but sort to same contents
            return 'sortsame'
    
    # everything checks out
    return 'pass'

def printProgress(msgq, numTests, numProcs):
    # setup indicator characters
    chrPass="[32m*[0m"
    chrSort="[33m^[0m"
    chrStdErr="[34mo[0m"

    # maintain test stats
    stats = {
        'total': 0,
        'passed': 0,
        'sortsame': 0,
        'stderr': 0,
    }

    # get size of terminal (thanks: stackoverflow.com/questions/566746/)
    rows, cols = os.popen('stty size', 'r').read().split()
    cols = int(cols)

    # figure size of printed area
    printrows = int(math.ceil(float(numTests) / (cols-2)))

    # move forward for blank lines to hold progress bars
    for i in range(printrows + 1):
        print
    # print '.' for every test to be run
    for i in range(numTests):
        x = i % (cols-2) + 2
        y = i / (cols-2)
        printAt(x, printrows-y, '.')

    numDone = 0
    while numDone < numProcs:

        msg = msgq.get()

        if msg == 'done':
            numDone += 1
        else:
            testid, result = msg

            # print correct mark, update stats
            if result == 'start':
                c = ':'
                stats['total'] += 1
            elif result == 'pass':
                c = chrPass
                stats['passed'] += 1
            elif result == 'sortsame':
                c = chrSort
                stats['passed'] += 1
                stats['sortsame'] += 1
            elif result == 'stderr':
                c = chrStdErr
                stats['stderr'] += 1

            x = testid % (cols-2) + 2
            y = testid / (cols-2)
            printAt(x, printrows-y, c)

    if mode == "run" or mode == "runp":
        # report stats
        print
        print " %s : %2d / %2d  Passed" % \
                (chrPass, stats['passed'], stats['total'])
        if stats['sortsame'] > 0:
            print " %s : %2d       Different order, same contents" % \
                    (chrSort, stats['sortsame'])
        if stats['stderr'] > 0:
            print " %s : %2d       Produced output to STDERR" % \
                    (chrStdErr, stats['stderr'])

# x is 1-based
# y is 0-based, with 0 = lowest row, 1 above that, etc.
def printAt(x,y, string):
    # move to correct position
    sys.stdout.write("[%dF" % y)  # y (moves to start of row)
    sys.stdout.write("[%dG" % x)         # x

    sys.stdout.write(string)

    # move back down
    sys.stdout.write("[%dE" % y)

    # move cursor to side and flush anything pending
    sys.stdout.write("[999G")
    sys.stdout.flush()

def main():
    global mode, testexe, verbose

    if len(sys.argv) >= 2:
        mode = sys.argv[1]

    if len(sys.argv) >= 3:
        testexe = sys.argv[2]

    validmodes = ['run','runp','runverbose','nocheck','regenerate']

    if mode not in validmodes:
        print "Invalid mode: %s" % mode
        print "Options:", (", ".join(validmode))
        return 1

    if mode =='runverbose':
        verbose = True
        mode = 'run'
    elif mode == 'regenerate':
        sure = raw_input("Are you sure you want to regenerate all test outputs (y/n)? ")
        if sure.lower() != 'y':
            print "Exiting."
            return 1
    if mode == "runp":
        # run tests in parallel
        numProcs = cpu_count()
    else:
        # run, nocheck, and regenerate are done serially.
        #  (nocheck is best for timing, and regenerate
        #  can have issues with output file clashes.)
        numProcs = 1

    # say what we are about to do
    report = "Running all tests"
    if testexe != '':
        report += " for " + testexe
    if mode == 'nocheck':
        report += " (skipping results checks)"
    if mode == 'regenerate':
        report += " (to regenerate output files)"
    report += "."
    print report

    # run the tests
    jobq = makeTests()
    numTests = jobq.qsize()
    msgq = Queue()
    for pid in range(numProcs):
        p = Process(target=runTests, args=(jobq,msgq,pid,))
        p.daemon = True
        p.start()

    # wait for completion, printing progress/stats as needed
    try:
        if not verbose:
            printProgress(msgq, numTests, numProcs)
        jobq.join()
    except KeyboardInterrupt:
        pass

if __name__=='__main__':
    main()

