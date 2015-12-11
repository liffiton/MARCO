# Test configuration
# Syntax: Python

import glob

reg_files = []
reg_files.extend(glob.glob('*.cnf'))
reg_files.extend(glob.glob('*.gcnf'))
reg_files.extend(glob.glob('*.smt2'))
reg_files.extend(glob.glob('*.gz'))

rnd3sat_files = glob.glob('3sat_n10/*.cnf')

common_flags = '-v'
# for systems on which MUSer cannot run
#common_flags += ' --force-minisat'

# old tests
#test_set_flags = ['--nomax', '-m always', '-m half', '-M'],
#test_set_flags += ['-b MCSes --nomax', '-b MCSes -m always', '-b MCSes -m half', '-b MCSes -M'],

test_set_flags = [
        '', '-b MCSes', '--parallel MUS', '--parallel MUS,MUS', '--parallel MUS,MCS', '--parallel MUS,MCSonly'
        ]

cmd = '../marco.py'

jobs = [
    # Random 3SAT
    {
      'name':    '3sat',
      'files':   rnd3sat_files,
      'flags':   test_set_flags,
      'flags_all': common_flags,
      'default': False,
    },
    # SMUS
    {
      'name':    'smus',
      'files':   reg_files,
      'flags':   ['--smus'],
      'flags_all': common_flags,
      'exclude': ['dlx2_aa.cnf'],
      'out_filter': 'S',
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
    # --pmuser
    {
      'name':    'marco_py',
      'files':   reg_files,
      'flags':   ['--pmuser 2'],
      'flags_all': common_flags,
      'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
      'default': True,
    },
    # --force-minisat
    {
      'name':    'marco_py',
      'files':   reg_files,
      'flags':   ['--force-minisat'],
      'flags_all': common_flags,
      'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
      'default': True,
    },
]
