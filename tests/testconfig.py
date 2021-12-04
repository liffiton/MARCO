# Test configuration
# Syntax: Python

import glob
import subprocess
import sys

interpreter = sys.executable  # use whatever interpreter is running this script
cmd = '../marco.py'
cmd_array = [interpreter, cmd]

common_flags = '-v'

test_set_flags = [
    '', '-b MCSes', '--nomax', '--threads 1', '--parallel MUS,MCS', '--parallel MUS,MCSonly'
]

# check for systems on which MUSer cannot run
ret = subprocess.call(cmd_array + ['--check-muser'])
if ret > 0:
    print("[33m  Adding '--force-minisat' flag to all runs.[m")
    print("")
    common_flags += ' --force-minisat'
    muser_available = False
else:
    muser_available = True

# collect test instances
reg_files = []
reg_files.extend(glob.glob('*.cnf'))
reg_files.extend(glob.glob('*.gcnf'))
reg_files.extend(glob.glob('*.gz'))
# check for z3, add SMT files if available
try:
    import z3  # noqa
    reg_files.extend(glob.glob('*.smt2'))
except ImportError:
    print("Unable to import z3 module.\n[33m  Skipping SMT tests.[m")
    print("")

rnd3sat_files = glob.glob('3sat_n10/*.cnf')

jobs = [
    # Random 3SAT
    {
      'name':    '3sat',
      'files':   rnd3sat_files,
      'flags':   test_set_flags,
      'flags_all': common_flags,
      'default': False,
    },
    # "Normal" tests
    {
      'name':    'marco_py',
      'files':   reg_files,
      'flags':   test_set_flags,
      'flags_all': common_flags,
      'default': True,
    },
    # --rnd-init
    {
      'name':    'marco_py',
      'files':   reg_files,
      'flags':   ['--rnd-init 54321'],
      'flags_all': common_flags,
      'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
      'default': True,
    },
]
jobs.extend([
    # Test some options on fewer instances
    {
    'name':    'marco_py',
    'files':   reg_files,
    'flags':   ['--comms-disable', '--comms-ignore', '--all-randomized', '--improved-implies'],
    'flags_all': common_flags,
    'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
    'default': True,
    },
])
if muser_available:
    jobs.extend([
        # --force-minisat
        {
        'name':    'marco_py',
        'files':   reg_files,
        'flags':   ['--force-minisat'],
        'flags_all': common_flags,
        'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
        'default': True,
        },
    ])
