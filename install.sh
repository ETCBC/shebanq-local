#!/bin/bash

HELP="
Invoked by start.sh as entry point of the shebanq container.
Or manually invoked within a running container.
Installs and configures software.
No arguments needed.
Working directory: any.
"

if [[ $1 == "--help" || $1 == "-h" ]]; then
    printf "$HELP"
    exit
fi

appdir=/app
srcdir=$appdir/src
rundir=$appdir/run
cfgdir=$rundir/cfg
logdir=$rundir/log

web2pydir=$rundir/web2py
mysqloptfile=$cfgdir/mysql.opt

shebanqdir=$rundir/shebanq
shebanqappdir=$web2pydir/applications/shebanq
adminappdir=$web2pydir/applications/admin

#----------------------------------------------------------------------------------
# Config files (always, env var may have changed)
#----------------------------------------------------------------------------------

if [[ ! -d $cfgdir ]]; then
    mkdir -p $cfgdir
fi

echo "
[mysql]
password = '$mysqlrootpwd'
user = $mysqlroot
host = $mysqlhost

[mysqldump]
password = '$mysqlrootpwd'
user = $mysqlroot
host = $mysqlhost
    " > $mysqloptfile

echo "$mysqluser" > $cfgdir/muser.cfg
echo "$mysqluserpwd" > $cfgdir/mql.cfg
echo $mysqlhost > $cfgdir/host.cfg
echo $web2pyadminpwd > $cfgdir/web2py.cfg
# echo -e "server = mail0.diginfra.net\nsender = dirk.roorda@di.huc.knaw.nl" > $cfgdir/mail.cfg
echo -e "server = localhost\nsender = shebanq@localhost" > $cfgdir/mail.cfg

echo "config files created" 

#----------------------------------------------------------------------------------
# Log dir (always make sure the log dir exists and is writable by Apache)
#----------------------------------------------------------------------------------

if [[ ! -e $logdir ]]; then
    mkdir $logdir
fi

chown www-data:www-data $logdir

#----------------------------------------------------------------------------------
# Web2Py
#----------------------------------------------------------------------------------

if [[ -f $web2pydir ]]; then
    rm -rf $web2pydir
fi
if [[ -d $web2pydir ]]; then
    existweb2py="v"
    action="updated"
else
    existweb2py="x"
    action="installed"
fi
if [[ "$doupdate" == "update" || $existweb2py == "x" ]]; then
    web2pyfile=web2py-shb.zip
    web2pyappdir=$web2pydir/applications
    adminappdir=$web2pyappdir/admin

    cp $srcdir/$web2pyfile $rundir/web2py.zip
    cd $rundir
    unzip web2py.zip > /dev/null
    rm web2py.zip

    # put custom files in place

    cp $srcdir/routes.py $web2pydir
    cp $srcdir/wsgihandler.py $web2pydir
 
    # hook up shebanq in web2py/applications

    if [[ -e $shebanqdir ]]; then
        if [[ ! -e $shebanqappdir ]]; then
            ln -sf ../../shebanq $shebanqappdir
        fi
    fi

    # remove the examples application
    # (if we remove the welcome application, web2py will complain)

    for app in examples
    do
        if [[ -e $web2pyappdir/$app ]]; then
            rm -rf $web2pyappdir/$app
        fi
    done
    for fl in NEWINSTALL
    do
        if [[ -e $web2pydir/$fl ]]; then
            rm -rf $web2pydir/$fl
        fi
    done

    # make certain dirs of admin app writable

    for wd in log cache errors sessions private uploads languages
    do
        wdpath=$adminappdir/$wd
        if [[ ! -e $wdpath ]]; then
            mkdir $wdpath
            chown www-data:www-data $wdpath
        fi
    done

    # compile admin app

    generatedDir=$adminappdir/compiled
    if [[ ! -e $generatedDir ]]; then
        mkdir $generatedDir
        # chown www-data:www-data $generatedDir
    fi
    cmd1="import gluon.compileapp;"
    cmd2="gluon.compileapp.compile_application('applications/admin')"

    # python-compile modules of admin app

    cd $web2pydir
    python3 -c "$cmd1 $cmd2" > /dev/null
    cd $adminappdir
    python3 -m compileall modules > /dev/null
    generatedDir=$adminappdir/modules/__pycache__
    # chown -R www-data:www-data $generatedDir
    cd $appdir

    echo "web2py $action"
else
    echo "using existing web2py without updating"
    printf "do\n    ./shebanq.sh up update\nto update web2py.\n"
fi

# set the admin password (always, env var may have changed)

cd $web2pydir
python3 -c "from gluon.main import save_password; save_password('''$web2pyadminpwd''', $hostport)"
python3 -c "from gluon.main import save_password; save_password('''$web2pyadminpwd''', 443)"
python3 -c "from gluon.main import save_password; save_password('''$web2pyadminpwd''', 80)"
cd $appdir

#----------------------------------------------------------------------------------
# Install SHEBANQ
#
# Changes in shebanq will be copied from src/shebanq to run/shebanq
# But the dynamic directories in run/shebanq will not be overwritten
#----------------------------------------------------------------------------------

compileneeded=v

if [[ -f $shebanqdir ]]; then
    rm -rf $shebanqdir
fi
if [[ -d $shebanqdir ]]; then
    existshebanq="v"
    action="updated"
else
    existshebanq="x"
    action="installed"
fi
if [[ "$doupdate" == "update" || $existshebanq == "x" ]]; then
    mkdir -p $shebanqdir
    compileneeded=v

    shebanqsrcdir=$srcdir/shebanq

    # copy over the missing subdirectories

    for subdir in $shebanqsrcdir/*
    do
        subname=`basename $subdir`
        rsync -av --delete --exclude '__pycache__' $subdir $shebanqdir/
        compileneeded=v
    done

    # make certain dirs in the shebanq app writable

    for wd in log cache errors sessions private uploads databases languages
    do
        for basedir in $shebanqdir $adminappdir
        do
            subdest=$basedir/$wd
            if [[ ! -d $subdest ]]; then
                mkdir $subdest
                chown www-data:www-data $subdest
            fi
        done
    done

    # Configure Web2Py and SHEBANQ

    if [[ ! -e $shebanqappdir ]]; then
        ln -sf ../../shebanq $shebanqappdir
    fi

    # compile shebanq app

    if [[ $compileneeded == v ]]; then
        echo "compiling app ..."
        generatedDir=$shebanqdir/compiled
        if [[ ! -e $generatedDir ]]; then
            mkdir $generatedDir
            chown -R www-data:www-data $generatedDir
        fi
        cmd1="import gluon.compileapp;"
        cmd2="gluon.compileapp.compile_application('applications/shebanq')"
        cmd3="gluon.compileapp.compile_application('applications/admin')"

        cd $web2pydir
        python3 -c "$cmd1 $cmd2" > /dev/null
        python3 -c "$cmd1 $cmd3" > /dev/null

        cd $shebanqappdir
        python3 -m compileall modules > /dev/null
        generatedDir=$shebanqdir/modules/__pycache__
        python3 -m compileall models > /dev/null
        generatedDir=$shebanqdir/models/__pycache__
        chown -R www-data:www-data $generatedDir

        cd $adminappdir
        python3 -m compileall modules > /dev/null
        generatedDir=$adminappdir/modules/__pycache__
        python3 -m compileall models > /dev/null
        generatedDir=$adminappdir/models/__pycache__
        chown -R www-data:www-data $generatedDir
    fi

    echo "shebanq $action"
else
    echo "using existing shebanq without updating"
    printf "do\n    ./shebanq.sh up update\nto update shebanq.\n"
fi
