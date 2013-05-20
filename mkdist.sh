#!/bin/bash

shopt -s extglob
marco_files=@(*.py|README)
minisolvers_files=`find pyminisolvers/ -name "*.cc" -or -name "*.cpp" -or -name "*.h" -or -name "Makefile" -or -name "makefile" -or -name "*.py"`
test_files=tests/*.@(cnf|smt2|gz)
tar czvhf marco_py.tar.gz $marco_files $minisolvers_files $test_files

