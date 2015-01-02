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
    output_file=$(mktemp /tmp/tmp.XXXXXXX)
    concat_cmd=$(echo "$@" | xargs echo)
    eval "${concat_cmd}" > "${output_file}" 2>&1  &
    command_pid=$!
    
    # This is effectively a tool to feed the travis-ci script
    # watchdog. Print a dot every sixty seconds.
    echo "while :; sleep 60; do printf '.'; done" | bash 2> /dev/null &
    printer_pid=$!
    
    wait "${command_pid}"
    command_result=$?
    kill "${printer_pid}"
    wait "${printer_pid}" 2> /dev/null
    if [[ $command_result != 0 ]] ; then
        failures=$((failures + 1))
        cat "${output_file}"
        printf "\nA subcommand failed. "
        printf "Consider deleting the travis build cache.\n"
    fi
}

function setup_pandoc() {
    if [[ $use_pandoc == 1 ]] ; then
        if which cabal ; then
            printf "\n=> Installing documentation tools"
            printf "\n    ... Installing pandoc "
            check_status_of cabal install pandoc
            printf "\n   ... Installing doc converters (pypandoc, "
            printf "setuptools-markdown) "
            check_status_of pip install setuptools-markdown
        else
            printf "\nERROR: haskell language must be activated. Consider "
            printf "using setup-lang.sh -l haskell to activate it."
        fi
    fi
}

setup_pandoc

printf "\n=> Installing python project and dependencies"

printf "\n   ... Installing project"
check_status_of python setup.py install
check_status_of python setup.py clean --all
rm -rf build
rm -rf dist

printf "\n   ... Installing test dependencies"
check_status_of pip install -e ".[test]" --process-dependency-links

exit ${failures}
