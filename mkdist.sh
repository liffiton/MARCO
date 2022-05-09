#!/bin/bash

# gather "whitelist" of files to include
marco_files="*.py src/marco/*.py src/marco/muser2-para README* CHANGES* VERSION"
if [ $# -lt 2 -o "$2" != "notest" ] ; then
    test_files="tests/*.cnf tests/*.gcnf tests/*.smt2 tests/*.gz tests/*.py tests/out/*/*"
fi
minisolvers_files=`find src/pyminisolvers/ \( -name "*.cc" -or -name "*.cpp" -or -name "*.h" -or -name "Makefile" -or -name "makefile" -or -name "*.py" -or -name "*.pyx" \) -print`

if [ "$1" = "list" ] ; then
    echo "Selected files:"
    for f in $marco_files $test_files $minisolvers_files ; do
        echo $f
    done
    exit 0
fi

# setup temp named dir
if [ "$1" = "commit" ] ; then
    version=`date +%Y%m%d`-`git rev-parse --short HEAD`
else
    version=`cat VERSION`
fi
dir=marco_py-$version
if [ -e $dir ] ; then
    echo "WHOA WHOA WHOA...  $dir exists?!  Not going to touch that..."
    exit
fi
mkdir $dir

# copy files into temp dir
echo "Copying..."
for file in $marco_files $test_files $minisolvers_files ; do
    echo "  $file"
    mkdir -p $dir/`dirname $file`/
    cp $file $dir/`dirname $file`/
done

echo

# tar!
echo "Tar-ing..."
tar czvhf $dir.tar.gz $dir

# cleanup
rm -r $dir

# save dist file
mkdir -p dist
mv $dir.tar.gz dist
echo
echo "$dir.tar.gz created in dist/"

