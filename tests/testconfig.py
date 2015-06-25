# Test configuration
# Syntax: Python

import glob

reg_files = []
reg_files.extend(glob.glob('*.cnf'))
reg_files.extend(glob.glob('*.gcnf'))
reg_files.extend(glob.glob('*.smt2'))
reg_files.extend(glob.glob('*.gz'))

rnd3sat_files = glob.glob('3sat_n10/*.cnf')

common_flags = ['-v']
# for systems on which MUSer cannot run
#common_flags.append('--force-minisat')

cmd = '../marco.py'

jobs = [
    # Random 3SAT, testing a new mode.
    {
      'name':    '3sat_new',
      'cmd':     cmd,
      'files':   rnd3sat_files,
      'flags':   ['--force-shrinkusemss', '--improved-implies'],
      'flags_all': ['-v', '--use-singletonMCSes', '--force-minisat'],
      'default': False,
    },
    # Random 3SAT
    {
      'name':    '3sat',
      'cmd':     cmd,
      'files':   rnd3sat_files,
      'flags':   ['--nomax', '-m always', '-m half', '-M', '--mssguided', '--ignore-implies'],
      'flags_all': common_flags,
      'default': False,
    },
    {
      'name':    '3sat',
      'cmd':     cmd,
      'files':   rnd3sat_files,
      'flags':   ['--nomax', '-m always', '-m half', '-M', '--mssguided', '--ignore-implies'],
      'flags_all': common_flags + ['-b', 'MCSes'],
      'default': False,
    },
    # SMUS
    {
      'name':    'smus',
      'cmd':     cmd,
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
      'cmd':     cmd,
      'files':   reg_files,
      'flags':   ['', '--nomax', '-m always', '-m half', '-M', '--mssguided', '--ignore-implies'],
      'flags_all': common_flags,
      'default': True,
    },
    {
      'name':    'marco_py',
      'cmd':     cmd,
      'files':   reg_files,
      'flags':   ['', '--nomax', '-m always', '-m half', '-M', '--mssguided', '--ignore-implies'],
      'flags_all': common_flags + ['-b','MCSes'],
      #'exclude': ['dlx2_aa.cnf'],
      'default': True,
    },
    # --block-both requires output filters
    {
      'name':    'marco_py',
      'cmd':     cmd,
      'files':   reg_files,
      'flags':   ['--block-both'],
      'flags_all': common_flags,
      'out_filter': 'S',
      'default': True,
    },
    {
      'name':    'marco_py',
      'cmd':     cmd,
      'files':   reg_files,
      'flags':   ['-b MCSes --block-both'],
      'flags_all': common_flags,
      'out_filter': 'U',
      'default': True,
    },
    # --force-minisat
    {
      'name':    'marco_py',
      'cmd':     cmd,
      'files':   reg_files,
      'flags':   ['', '--mssguided', '--ignore-implies'],
      'flags_all': common_flags + ['--force-minisat'],
      'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
      'default': True,
    },
]
