#!/usr/bin/env python

import os
import signal
import sys
from z3 import *

def read_constraints(filename):
    if filename.endswith('.cnf'):
        return read_dimacs(filename)
    else:
        return read_smt2(filename)

def read_dimacs(filename):
    formula = []
    with open(filename) as f:
        for line in f:
            if line.startswith('c') or line.startswith('p'):
                continue
            clause = [int(x) for x in line.split()[:-1]]
            formula.append( Or( [var(i) for i in clause] ) )
    return formula
            

def read_smt2(filename):
    formula = parse_smt2_file(filename)
    if is_and(formula):
        return formula.children()
    else:
        return [formula]

c_prefix = "!marco_"

def setup_solver(s, constraints):
    for i in range(len(constraints)):
        v = var(i, c_prefix)
        s.add(Implies(v, constraints[i]))

def var(i, prefix=''):
#    if prefix not in var.cache:
#        var.cache[prefix] = {}
    if i not in var.cache[prefix]:
        if i >= 0:
            var.cache[prefix][i] = Bool(prefix+str(i))
        else:
            var.cache[prefix][i] = Not(Bool(prefix+str(-i)))
    return var.cache[prefix][i]
# "static" dictionaries for caching vars
var.cache = {}
var.cache[c_prefix] = {}
var.cache[''] = {}

def to_c_lits(seed):
    return [var(i,c_prefix) for i in seed]

def complement(aset, n):
    return set(range(n)) - aset

def check_subset(s, seed):
    assumptions = to_c_lits(seed)
    return s.check(assumptions)

def shrink(s, seed):
    current = set(seed)
    for i in seed:
#        if i not in current:
#            # May have been "also-removed"
#            continue
        if check_subset(s, current - set([i])) == unsat:
            # Remove any also-removed constraints
            #current = seed_from_core(s.unsat_core())  # doesn't seem to help much (I think the subset is almost always sat)
            current.remove(i)
    return current

def grow(s, seed, n):
    current = set(seed)
    for i in complement(current, n):
#        if i in current:
#            # May have been "also-satisfied"
#            continue
        if check_subset(s, current | set([i])) == sat:
            # Add any also-satisfied constraint
            #current = seed_from_model(s.model(), n)  # still too slow to help here
            current.add(i)
    return current

def name_to_int(name):
    return int(name.split('_')[-1])

def seed_from_core(core):
    return set([name_to_int(i.decl().name()) for i in core])

def seed_from_model(model, n):
    ''' Works for models both from map and from solver, as long as both use integer, 0-based literals with c_prefix for the constraints '''
    seed = set(range(n))  # default to all True for "high bias"
#    for i in range(n):
#        x = var(i, c_prefix)
#        if is_false(model.eval(x)):
#            seed.remove(i)
    for x in model:
        if x.name().startswith(c_prefix):
            if is_false(model[x]):
                seed.remove(name_to_int(x.name()))
    return seed

def block_down(s, frompoint, n):
    comp = complement(frompoint, n)
    if comp:
        s.add( Or( to_c_lits(comp) ) )
    else:
        # *could* be empty (if instance is SAT)
        s.add(False)

def block_up(s, frompoint):
    if frompoint:
        s.add( Or( [Not(x) for x in to_c_lits(frompoint)] ) )
    else:
        # *could* be empty (if instance is SAT)
        s.add(False)

def sighandler(signum, frame):
    print signum
    print frame
    main_ctx().interrupt()
    print "interrupted???"

def enumerate_infeasibility(solver, n):
    s_map = Solver()

    while s_map.check() == sat:
        #print s_map.assertions()
        #print solver.assertions()
        seed = seed_from_model(s_map.model(), n)
        #print "Seed:", seed
        if check_subset(solver, seed) == sat:
            #print "Growing..."
            #seed = seed_from_model(solver.model(), n)  # still too slow to help here
            MSS = grow(solver, seed, n)
            yield ("MSS", MSS)
            block_down(s_map, MSS, n)
        else:
            #print "Shrinking..."
            seed = seed_from_core(solver.unsat_core())
            MUS = shrink(solver, seed)
            yield ("MUS", MUS)
            block_up(s_map, MUS)

def main():
    if len(sys.argv) < 2:
        print "Usage: %s FILE.smt" % sys.argv[0]
        sys.exit(1)
    filename = sys.argv[1]
    if not os.path.exists(filename):
        print "File does not exist: %s" % filename
        sys.exit(1)

    solver = Solver()
    constraints = read_constraints(sys.argv[1])
    setup_solver(solver, constraints)

    n = len(constraints)

    # Simple tests
    #full = range(n)
    #empty = []
    #print shrink(solver, full)
    #print grow(solver, empty, n)

    # TODO: run enumerate_infeasibility() in a separate thread or process
    #       install signal handler to main_ctx().interrupt() it
    x = 0
    for result in enumerate_infeasibility(solver, n):
        print result[0], len(result[1])
        x += 1
        #if x > 40:
        #    return
        #print result[0], result[1]

if __name__ == '__main__':
    main()

