# Test configuration
# Syntax: Python

import glob

files = []
# Each entry is a list: [INFILE] or [INFILE,OUTFILE]
# INFILE is found in the "in/" subdirectory.
# OUTFILE is found in the "out/" subdirectory,
#  and it is derived from INFILE (adding '.out') if none is specified.
files.extend(glob.glob('*.cnf'))
files.extend(glob.glob('*.smt2'))
files.extend(glob.glob('*.gz'))
files = [[x] for x in files]

common_flags = ['-v']

exes = [
    {
      'name':    'marco_py', 
      'cmd':     '../marco.py',
      'flags':   ['', '-b low', '-m', '-m -b low'],
    },
    {
      'name':    'marco_py_smus', 
      'cmd':     '../marco.py',
      'flags':   ['--smus'],
    },
]
