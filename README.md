MARCO: an efficient MUS and MSS/MCS enumeration tool
====================================================

This is a Python implementation of the MARCO/MARCOs algorithm [1,2] for
enumerating MUSes and MSS/MCSes of infeasible constraint systems (currently:
CNF, GCNF, and SMT).  This implementation makes use of MUSer2 [3,4] for MUS
extraction and MiniSAT 2.2 [5] for satisfiability testing and the generation of
SAT models.

   Website: https://www.iwu.edu/~mliffito/marco/

Please contact Mark Liffiton (mliffito@iwu.edu) in case of any errors or
questions.

[1] MARCO
   M. Liffiton, A. Previti, A. Malik, and J. Marques-Silva (2016)
   "Fast, Flexible MUS Enumeration." In: Constraints 21(2):223-250.

[2] MARCOs (parallel MARCO)
   W. Zhao and M. Liffiton (2016) "Parallelizing Partial MUS Enumeration."
   In: Proc. ICTAI 2016.

[3] MUSer2
   A. Belov and J. Marques-Silva (2012) "MUSer2: An efficient MUS extractor."
   In: Journal on Satisfiability, Boolean Modeling and Computation 8, 123-128.

[4] MUSer2 (parallel)
   A. Belov, N. Manthey, and J. Marques-Silva (2013) "Parallel MUS extraction."
   In: Proc. SAT 2013.

[5] Minisat 2.2
   N. Een and N. Sörensson (2003) "An Extensible SAT-solver." In: Proc. SAT 2003.
   N. Een and A. Biere (2005) "Effective Preprocessing in SAT through Variable
   and Clause Elimination." In: Proc. SAT 2005. 


## Setup

This implementation makes use of Python bindings for MiniSAT that must be built
before running MARCO.

Tested Platforms:

 - Linux
 - Cygwin
 - OS X

Requirements:

 - Python 3.x
 - A standard build environment (make, gcc or clang, etc.)
 - zlib development libraries (e.g., `zlib1g-dev` or `zlib-devel` packages)

To build and test the Python bindings:

    $ cd src/pyminisolvers
    $ make
    $ make test

Additionally, the following are recommended, depending on your needs:

 - Z3 Python interface for analyzing SMT instances.

     Available as part of the Z3 distribution: https://github.com/Z3Prover/z3

     Installable via `pip`:  `pip install z3-solver`

 - A MUSer2 binary for analyzing CNF/GCNF.  The included `muser2-para` binary
   is compiled for x86-64 Linux.  For other platforms, download and compile
   from the source (license: GPL).

     Available from: https://bitbucket.org/anton_belov/muser2-para

   Without a working MUSer2 binary, you can still run MARCO on CNF/GCNF in a
   fall-back mode that uses a basic, *much less efficient* deletion-based MUS
   extractor using Minisat directly (see the `--force-minisat` option).


## Usage

Example: `./marco.py tests/test1.cnf`

Run `./marco.py --help` for a list of available options.

Input files may be in CNF, GCNF (group oriented CNF), or SMT2 format.  Input
files may be gzipped.

The supported GCNF format is specified in:
  http://www.satcompetition.org/2011/rules.pdf

The output lists MUSes ("U") and MSSes ("S"), one per line.  In 'verbose' mode
(-v), each line also lists the indexes of the constraints included in each set
(with 1-based counting).  MCSes are the complements of the MSSes w.r.t. the
original set of input constraints (e.g., if MARCO reports an MSS "1 3 4" for a
5-constraint input, the corresponding MCS is constraints 2 and 5).  If you want
the MCSes printed directly, use the '--print-mcses' command line option; MCSes
will be printed on lines starting with "C" (in place of the "S" lines for their
MSSes).

### Library/API Usage

All functionality is accessible via a simple API that mirrors the command line
interface.  See `lib_examples.py` for examples.  Most options listed in
`./marco.py --help` can be used (excluding any that don't make sense for use
in the context of running as part of another program).


## Authors
- MARCO: Mark Liffiton and Wenting Zhao

### Included solvers
- MUSer2: Anton Belov, Norbert Manthey, and Joao Marques-Silva
- MiniSAT: Niklas Een and Niklas Sörensson
- MiniCARD: Mark Liffiton and Jordyn Maglalang
