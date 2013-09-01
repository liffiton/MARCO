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

jobs = [
    {
      'name':    '3sat',
      'cmd':     '../marco.py',
      'files':   rnd3sat_files,
      'flags':   ['', '-m', '-M', '--mssguided', '--nogrow', '--half-max'],
      'flags_all': common_flags,
      'default': False,
    },
    {
      'name':    'smus',
      'cmd':     '../marco.py',
      'files':   reg_files,
      'flags':   ['--smus'],
      'flags_all': common_flags,
      'exclude': ['dlx2_aa.cnf'],
      'default': False,
    },
    {
      'name':    'marco_py',
      'cmd':     '../marco.py',
      'files':   reg_files,
      'flags':   ['', '-m', '-M', '--mssguided', '--nogrow', '--half-max'],
      'flags_all': common_flags,
      'default': True,
    },
    {
      'name':    'marco_py',
      'cmd':     '../marco.py',
      'files':   reg_files,
      'flags':   ['', '-m', '-M', '--mssguided', '--nogrow', '--half-max', '--ignore-singletons'],
      'flags_all': common_flags + ['--force-minisat'],
      'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
      'default': True,
    },
    {
      'name':    'marco_py',
      'cmd':     '../marco.py',
      'files':   reg_files,
      'flags':   ['', '-m', '-M', '--mssguided', '-m --mssguided', '--half-max', '--ignore-singletons'],
      'flags_all': common_flags + ['-b','low','-a','MCSes'],
      'exclude': ['dlx2_aa.cnf'],
      'default': True,
    },
    {
      'name':    'marco_py',
      'cmd':     '../marco.py',
      'files':   reg_files,
      'flags':   ['', '-m', '--mssguided', '-m --mssguided', '--half-max', '--ignore-singletons'],
      'flags_all': common_flags + ['-b','none','-a','MUSes'],
      'exclude': ['dlx2_aa.cnf'],
      'default': True,
    },
]
