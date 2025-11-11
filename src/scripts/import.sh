#!/bin/bash

# Script to import data into a SHEBANQ server.
# Run it on the server.
# It imports data from the result of an mysqldump --tab action

USAGE="
Usage: ./import.sh

Import databases that contain dynamic website data of SHEBANQ:

*   shebanq_web
*   shebanq_note

"

mcfg="/app/run/cfg/mysql.opt"
backupdir="/app/backup"

for db in shebanq_note shebanq_web
do
    echo "dropping $db"
    mysql --defaults-extra-file="$mcfg" -e "drop database if exists $db;"
done

for db in shebanq_web shebanq_note
do
    mysql --defaults-extra-file="$mcfg" -e "create database $db;"
done

db=shebanq_web
echo "importing $db"
idir="$backupdir/$db"
cd "$idir"

for table in auth_user auth_group organization project \
    web2py_session_shebanq \
    auth_membership auth_permission auth_cas auth_event uploaders \
    query query_exe monads
do 
    sqlfile="$table.sql"; 
    mysql --defaults-extra-file="$mcfg" $db < $sqlfile
    echo "LOAD DATA LOCAL INFILE '$table.txt' INTO TABLE $table" | mysql --defaults-extra-file="$mcfg" $db
done

db=shebanq_note
echo "importing $db"
idir="$backupdir/$db"
cd "$idir"
table=note
sqlfile="$table.sql"; 
mysql --defaults-extra-file="$mcfg" $db < $sqlfile
echo "LOAD DATA LOCAL INFILE '$table.txt' INTO TABLE $table" | mysql --defaults-extra-file="$mcfg" $db
