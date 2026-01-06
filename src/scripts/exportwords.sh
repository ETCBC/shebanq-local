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
Usage: ./exportwords.sh

Exports the passage database for version 2021: shebanq_passage2021

The export ends up in the /app/backup directory on the deployment.
"

mcfg="/app/run/cfg/mysql.opt"
backupdir="/app/backup"

ensureDir "$backupdir"

echo "creating database export of shebanq_passage2021 in $backupdir"

db=shebanq_passage2021
echo "exporting $db"
edir="$backupdir/$db"
if [[ -e "$edir" ]]; then
    rm -rf "$edir"
fi
mkdir -p "$edir"
mysqldump --defaults-extra-file="$mcfg" --tab="$edir" $db
