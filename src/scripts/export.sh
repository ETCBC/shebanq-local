#!/bin/bash

# Script to export a SHEBANQ server.
# Run it on the server.

function ensureDir {
    if [[ -f "$1" ]]; then
        rm -rf "$1"
    fi
    if [[ ! -d "$1" ]]; then
        mkdir -p "$1"
    fi
}


USAGE="
Usage: ./export.sh

Exports databases that collect dynamic website data of SHEBANQ:

*   shebanq_web
*   shebanq_note

The exports end up in the /app/backup directory on the deployment.
"

mcfg="/app/run/cfg/mysql.opt"
backupdir="/app/backup"

ensureDir "$backupdir"

echo "creating database exports of shebanq_web and shebanq_note in $backupdir"

for db in shebanq_web shebanq_note
do
    echo "exporting $db"
    edir="$backupdir/$db"
    if [[ -e "$edir" ]]; then
        rm -rf "$edir"
    fi
    mkdir -p "$edir"
    mysqldump --defaults-extra-file="$mcfg" --tab="$edir" $db
done
