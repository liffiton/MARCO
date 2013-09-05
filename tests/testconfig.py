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

jobs = [
    {
      'name':    '3sat',
      'cmd':     '../marco.py',
      'files':   rnd3sat_files,
      'flags':   ['-a MUSes', '-a MCSes', '--nomax', '-m always', '-M always', '-m half', '-M half', '--mssguided', '--ignore-singletons'],
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
      'flags':   ['', '--nomax', '-m always', '-M always', '-m half', '-M half', '--mssguided', '--ignore-singletons'],
      'flags_all': common_flags,
      'default': True,
    },
    {
      'name':    'marco_py',
      'cmd':     '../marco.py',
      'files':   reg_files,
      'flags':   ['', '--nomax', '-m always', '-M always', '-m half', '-M half', '--mssguided', '--ignore-singletons'],
      'flags_all': common_flags + ['-a','MCSes'],
      'exclude': ['dlx2_aa.cnf'],
      'default': True,
    },
    {
      'name':    'marco_py',
      'cmd':     '../marco.py',
      'files':   reg_files,
      'flags':   ['', '--mssguided', '--ignore-singletons'],
      'flags_all': common_flags + ['--force-minisat'],
      'exclude': ['c10.cnf', 'dlx2_aa.cnf'],
      'default': True,
    },
]
