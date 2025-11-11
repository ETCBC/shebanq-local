#!/bin/bash

HELP="
Invoked by start.sh as entry point of the shebanq container.
Or manually invoked within a running container.
Loads data.
No arguments needed.
Working directory: any.
"

if [[ $1 == "--help" || $1 == "-h" ]]; then
    printf "$HELP"
    exit
fi

#mqlcmd=/opt/emdros/bin/mql
mqlcmd=/usr/local/bin/mql

appdir=/app
srcdir=$appdir/src
contentdir=$appdir/content
rundir=$appdir/run
tmpdir=$appdir/_temp

cfgdir=$rundir/cfg
mysqloptfile=$cfgdir/mysql.opt
mysqlasroot=--defaults-extra-file=$mysqloptfile
mysqlasroote="-h $mysqlhost -u $mysqlroot -p $mysqlrootpwd"


dbdir=$srcdir/databases

# set the permissions for the shebanq database user

# test which of the needed databases are already in mysql
# after this we have for each existing database a variable with name dbexists_databasename

mkdir -p $tmpdir

echo check existence of databases

for db in `echo "show databases;" | mysql $mysqlasroot`
do
    if [[ $db =~ ^shebanq_ ]]; then
        declare dbexists_$db=v
    fi
done

echo import the missing static databases

for version in 4 4b c 2017 2021
do
    db=shebanq_passage$version
    dbvar=dbexists_$db

    if [[ ${!dbvar} != v ]]; then
        echo Importing $db
        dbfile=$db.sql
        dbfilez=$dbfile.gz

        if [[ ! -e $tmpdir/$dbfile ]]; then
            echo -e "\tunzipping $db (takes approx.  5 seconds)"
            cp $dbdir/$dbfilez $tmpdir
            gunzip -f $tmpdir/$dbfilez
        fi
        echo -e "\tloading $db (takes approx. 15 seconds)"
        mysql $mysqlasroot < $tmpdir/$dbfile
        echo -e "\tdone"

        # clean up temp files
        if [[ -e $tmpdir/$dbfilez ]]; then
            rm -rf "$tmpdir/$dbfilez"
        fi
        if [[ -e $tmpdir/$dbfile ]]; then
            rm -rf "$tmpdir/$dbfile"
        fi
    fi

    echo "GRANT SELECT ON $db.* TO '$mysqluser'@'$mysqluserhost'" | mysql $mysqlasroot


    db=shebanq_etcbc$version
    dbvar=dbexists_$db

    if [[ ${!dbvar} != v ]]; then
        echo Importing $db
        dbfile=$db.mql
        dbfilez=$dbfile.bz2

        if [[ ! -e $tmpdir/$dbfile ]]; then
            echo -e "\tunzipping $db (takes approx. 75 seconds)"
            cp $dbdir/$dbfilez $tmpdir
            bunzip2 -f $tmpdir/$dbfilez
        fi
        mysql $mysqlasroot -e "drop database if exists $db;"
        echo -e "\tloading emdros $db (takes approx. 50 seconds)"
        $mqlcmd -e UTF8 -n -b m $mysqlasroote < $tmpdir/$dbfile
        echo -e "\tdone"

        # clean up temp files
        if [[ -e $tmpdir/$dbfilez ]]; then
            rm -rf "$tmpdir/$dbfilez"
        fi
        if [[ -e $tmpdir/$dbfile ]]; then
            rm -rf "$tmpdir/$dbfile"
        fi
    fi

    echo "GRANT SELECT ON $db.* TO '$mysqluser'@'$mysqluserhost';" | mysql $mysqlasroot
done

echo cleanup the dynamic databases

good=v

# Cleanup stage (only if the import of dynamic data is forced)
# The order note - web is important.


for kind in note web
do
    db=shebanq_$kind
    dbvar=dbexists_$db

    if [[ ${!dbvar} != v || $blankuserdata == v || $newuserdata == v ]]; then
        echo Checking $db
        dbfile=$db.sql
        dbfile_emp=${db}_empty.sql
        dbfilez=$dbfile.gz

        if [[ $blankuserdata != v && $newuserdata != v && -e $tmpdir/$dbfile ]]; then
            echo previous db content from temp directory
        else
            if [[ ( $blankuserdata != v || $newuserdata == v ) && -e $contentdir/$dbfilez ]]; then
                echo previous db content from content directory
                cp $contentdir/$dbfilez $tmpdir/$dbfilez
                echo unzipping $db
                gunzip -f $tmpdir/$dbfilez
            elif [[ -e $dbdir/$dbfile_emp ]]; then
                echo working with empty db
                cp $dbdir/$dbfile_emp $tmpdir/$dbfile
            else
                echo no data
                good=x
            fi
        fi
        if [[ $good == x ]]; then
            continue
        fi

        mysql $mysqlasroot -e "drop database if exists $db;"
        mysql $mysqlasroot -e "create database $db;"
    fi
done

# Import stage.
# The order web - note is important.

echo import the dynamic databases

for kind in web note
do
    db=shebanq_$kind
    dbvar=dbexists_$db
    if [[ $blankuserdata == v || $newuserdata == v || ${!dbvar} != v ]]; then
        dbfile=$db.sql

        if [[ -e $tmpdir/$dbfile ]]; then
            echo "use $db;\n" | cat - $tmpdir/$dbfile | mysql $mysqlasroot
            echo Imported $db
        else
            echo "Data file $dbfile does not exist in $tmpdir"
        fi
        # clean up temp files
        if [[ -e $tmpdir/$dbfile ]]; then
            rm -rf "$tmpdir/$dbfile"
        fi
    fi

    echo "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER ON $db.* TO '$mysqluser'@'$mysqluserhost';" | mysql $mysqlasroot
done
