#!/bin/bash

# READ THIS FIRST: maintenance.md

# Script to restore a server.
# Run it on the server.


USAGE="
Usage:

    ./restore.sh
    ./restore.sh ALL

Restores databases that collect dynamic website data of SHEBANQ:

*   shebanq_web
*   shebanq_note

The backups must be in the /app/backup directory on the deployment.

If ALL is passed, backup files with a names ending in -ALL are selected.
So shebanq_web-ALL.sql.gz instead of shebanq_web.sql.gz.
"

mcfg="/app/run/cfg/mysql.opt"
backupdir="/app/backup"

# order of dropping and creating is important!

if [[ "$1" == "ALL" ]]; then
    allrep="-all"
else
    allrep=""
fi

echo "unzipping database dumps for shebanq_web$allrep and shebanq_note$allrep"
gunzip -f $backupdir/shebanq_web$allrep.sql.gz -c > $backupdir/shebanq_web.sql
gunzip -f $backupdir/shebanq_note$allrep.sql.gz -c > $backupdir/shebanq_note.sql

echo "dropping and creating databases shebanq_web and shebanq_note"
mysql --defaults-extra-file="$mcfg" -e 'drop database if exists shebanq_note;'
mysql --defaults-extra-file="$mcfg" -e 'drop database if exists shebanq_web;'
mysql --defaults-extra-file="$mcfg" -e 'create database shebanq_web;'
mysql --defaults-extra-file="$mcfg" -e 'create database shebanq_note;'
echo "loading database shebanq_web$allrep"
echo "use shebanq_web" | cat - $backupdir/shebanq_web.sql | mysql --defaults-extra-file="$mcfg"
echo "loading database shebanq_note$allrep"
echo "use shebanq_note" | cat - $backupdir/shebanq_note.sql | mysql --defaults-extra-file="$mcfg"

sleep 2

rm -rf $backupdir/shebanq_web.sql
rm -rf $backupdir/shebanq_note.sql
