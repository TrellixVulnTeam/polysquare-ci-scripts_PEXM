#!/usr/bin/env bash
# /travis/python-install.sh
#
# Travis CI Script to run install a python project and its dependencies. Pass
# -p to use pandoc to convert the README file to the project's 
# long_description.
#
# See LICENCE.md for Copyright information

failures=0

while getopts "p" opt; do
    case "$opt" in
    p) use_pandoc=1
       ;;
    esac
done

function check_status_of() {
    concat_cmd=$(echo "$@" | xargs echo)
    eval "${concat_cmd}"
    if [[ $? != 0 ]] ; then
        failures=$((failures + 1))
    fi
}

function setup_pandoc() {
    if [[ $use_pandoc == 1 ]] ; then
        if which cabal ; then
            echo "=> Installing pandoc"
            cabal install pandoc
            echo "   ... Installing doc converters (pypandoc, " \
                "setuptools-markdown)"
            pip install setuptools-markdown
        else
            echo "ERROR: haskell language must be activated. Consider using " \
                     "setup-lang.sh -l haskell to activate it."
        fi
    fi
}

setup_pandoc

echo "=> Installing python project and dependencies"

echo "   ... Installing project"
check_status_of python setup.py install
check_status_of python setup.py clean --all
rm -rf build
rm -rf dist

echo "   ... Installing test dependencies"
check_status_of pip install -e ".[test]" --process-dependency-links

exit ${failures}
