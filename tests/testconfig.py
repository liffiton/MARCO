# Test configuration
# Syntax: Python

# Each entry is a list: [INFILE] or [INFILE,OUTFILE]
# INFILE is found in the "in/" subdirectory.
# OUTFILE is found in the "out/" subdirectory,
#  and it is derived from INFILE (adding '.out') if none is specified.
import glob
files = glob.glob('*.cnf')
files.extend(glob.glob('*.smt2'))
files.extend(glob.glob('*.gz'))
files = [[x] for x in files]

exes = [
    {
      'name':    'marco_py', 
      'cmd':     '../marco.py',
      'flags':   ['-v', '-v -m'],
    },
# e.g.:
#    {
#      'name':    'marco_py', 
#      'cmd':     '../marco.py',
#      'exclude': ['test6.cnf'],
#      'flags':   ['-v --force-minisat', '-v -m --force-minisat'],
#    },
]
