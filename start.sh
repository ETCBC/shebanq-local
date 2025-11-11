#!/bin/bash

HELP="
Entrypoint command of the shebanq container.
Installs software, loads data, and runs a service.
No arguments needed.
Working directory: any.
"

if [[ $1 == "--help" || $1 == "-h" ]]; then
    printf "$HELP"
    exit
fi



appdir=/app

echo verifying whether installation is complete
$appdir/install.sh
echo installation is complete

$appdir/load.sh
echo all data present in shebanqdb

echo starting shebanq web app
$appdir/run.sh $runmode &
pid=$!

trap "kill $pid" SIGTERM
wait "$pid"
