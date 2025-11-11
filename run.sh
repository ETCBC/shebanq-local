#!/bin/bash

HELP="
Invoked by start.sh as entry point of the shebanq container.
Or manually invoked within a running container.
Executes tests or service tasks.
Working directory: any.

TASKS

test-shebanq
    Just run the shebanq test controller

develop
    Run the web2py devserver in the foreground

production
    Run apache in the foreground.
    This is the default.
"

if [[ $1 == "--help" || $1 == "-h" ]]; then
    printf "$HELP"
    exit
fi

testshebanq=x

while [ ! -z $1 ]; do
    if [[ $1 == test-shebanq ]]; then
        testshebanq=v
        runmode=x
        shift
    elif [[ $1 == production ]]; then
        testshebanq=x
        runmode=production
        shift
    elif [[ $1 == develop ]]; then
        testshebanq=x
        runmode=develop
        shift
    else
        echo "unrecognized argument '$1'"
        testshebanq=x
        runmode=x
        good=x
        exit
    fi
done

# directories in the repo (persistently mounted into the shebanq image)

appdir=/app
rundir=$appdir/run

web2pydir=$rundir/web2py


if [[ $testshebanq == v ]]; then
    cd $web2pydir
    python3 web2py.py -S shebanq/hebrew/text -M > /dev/null
    exit
fi

if [[ $runmode == production ]]; then
    echo "PRODUCTION MODE (Apache)"
    apachectl -D FOREGROUND
fi

if [[ $runmode == develop ]]; then
    echo "DEVELOP MODE (web2py dev server)"
    cd $web2pydir
    python3 web2py.py --no_gui -i 0.0.0.0 -p $hostport -a $web2pyadminpwd
fi
