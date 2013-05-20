#!/bin/bash

# hack to get limited version of pyminisolvers
cd pyminisolvers ; git checkout minisat_only ; cd ..

# gather "whitelist" of files to include
marco_files="*.py muser2-static README VERSION"
test_files="tests/*.cnf tests/*.smt2 tests/*.gz tests/*.py tests/out/*"
minisolvers_files=`find pyminisolvers/ -name "*.cc" -or -name "*.cpp" -or -name "*.h" -or -name "Makefile" -or -name "makefile" -or -name "*.py"`

# setup temp named dir
version=`cat VERSION`
dir=marco_py-$version
if [ -e $dir ] ; then
    echo "WHOA WHOA WHOA...  $dir exists?!  Not going to touch that..."
    exit
fi
mkdir $dir

# copy files into temp dir
for file in $marco_files $test_files $minisolvers_files ; do
    echo $file
    mkdir -p $dir/`dirname $file`/
    cp $file $dir/`dirname $file`/
done

echo

# tar!
tar czvhf $dir.tar.gz $dir

# cleanup
rm -r $dir

# de-hack
cd pyminisolvers ; git checkout master ; cd ..
