#!/bin/bash

# Script to backup a SHEBANQ server.
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
Usage:

    ./backup.sh
    ./backup.sh ALL

Backs up databases that collect dynamic website data of SHEBANQ:

*   shebanq_web
*   shebanq_note

The backups end up in the /app/backup directory on the deployment.

If ALL is passed, backup files with a names ending in -ALL are created.
So shebanq_web-ALL.sql.gz instead of shebanq_web.sql.gz.
"

mcfg="/app/run/cfg/mysql.opt"
backupdir="/app/backup"

ensureDir "$backupdir"

if [[ "$1" == "ALL" ]]; then
    allrep="-all"
else
    allrep=""
fi

echo "creating database dumps of shebanq_web$allrep and shebanq_note$allrep in $backupdir"

for db in shebanq_web shebanq_note
do
    bufl="$backupdir/$db$allrep.sql.gz"
    mysqldump --defaults-extra-file="$mcfg" $db | gzip > "$bufl"
done
