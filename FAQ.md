# Frequently asked questions

## How do I run a query in this local SHEBANQ?

In order to run a (new) query in SHEBANQ, you have to log in.
You can go to the Login button and choose Sign up, in which case you will create
a new user. You have to supply an email addres and a password. 
Since it is a local deployment, you can keep the password simple.

Alternatively, if you had an account in the global SHEBANQ, you can continue to
use that, but you need to perform a few steps.

## Can I use my original account from the global SHEBANQ?

The accounts of all users of published queries are still in de local SHEBANQ,
but without their email addresses and passwords.
You have to look up your own name in the users table and supply an email address and
password there.

Here is how:

Open a  new terminal, got to your `shebanq-local` directory, and give the command:

```
./shebanq.sh browse admin
```

and fill out the password `wajehior`.

You are on a page titled **Available Databases and Tables**.
Click the 
[db.auth-user](http://localhost:8000/appadmin/select/db?query=db.auth_user)
table.

Find the row with your own name, and click the number in the first cell of that row.
In the form that is presented to you, fill out your email address and password.
You can enter short and easy values. The email address must look like an email
address, but it does not have to be an address that works.
The password must have a minimum length of 4 characters.
Click the *submit* button to save the change.

If you want to change your password later on, you also need to change your email
address, otherwise the system will complain that there is already an account with
that email address. You can work around it by changing the email address in a trivial
way, submitting, and then again changing the email address back to the original value,
and submit again.

Note that you can do all this also for any user that you find in the table, not only
for the user that is you. Because, after all, the whole shebanq is now your own
private copy.

## Do I need to maintain my local SHEBANQ?

Generally speaking: no.

But it is possible that the docker image for the local shebanq will be updated.
In that case you may or may not want to upgrade your local SHEBANQ. See the 
question about upgrading.

If you are a developer yourself, you might want to have more control.

First of all, here is some information:

1.  The docker images for shebanq only contain the supporting software, such as EMDROS
    and MariaDB, but not the source code of SHEBANQ and not the data.
1.  The source code of SHEBANQ is in this repo, in directory `src`.
1.  The data of the ETCBC databases is readonly, and stored in compressed form in
    `src/databases`.
1.  The user-contributed data of the global SHEBANQ is stored in the `content`
    directory. This data does not contain sensitive user data: only published
    queries and shared notes, and no email addresses and passwords.
1.  When the local SHEBANQ starts working, it uses the MariaDB image to set up a
    MYSQL database system, into which it imports the ETCBC databases from the 
    compressed sources, and the user databases from the initial content in
    `content`. This database system stores all this data in active form in the
    directory `data/mariadb`, which will be created if necessary, at the top-level
    of your `shebanq-local` repo. This `data` directory is in your `.gitignore` file,
    so it will not be synchronised to GitHub if you are in the position to push
    changes back.
    The import process only works for databases that have not already been imported.
    Every time you start up shebanq, this check willl be done.
1.  Also, when shebanq starts working, an active version of the source code files
    will be put in the `run` directory at the top-level of your `shebanq-local`
    repo, which is also in your `.gitignore` file.
1.  So all data pertaining to shebanq is in your local `shebanq-local` clone.

## How do I upgrade my local SHEBANQ?

If you got the information that there is a new version of the shebanq docker image 
on [docker hub](https://hub.docker.com/repository/docker/etcbc/shebanq/general),
look up the version and change it in the
[.env](https://github.com/ETCBC/shebanq-local/blob/master/.env)
file in your `shebanq-local` clone.

Stop your local shebanq if it is running, by

```
./shebanq.sh down
```

Then bring it up again by

```
./shebanq.sh up
```

Your local shebanq now runs in a container based on a new shebanq image.

You do not have to worry about your data: that is no touched at all by the upgrade
process.

## How do I reset the data in my local SHEBANQ?

The easiest way is to remove the `data/mariadb` directory and restart SHEBANQ.
The consequence is that all ETCBC databases have to be unpacked an imported again,
which will cost some time. And then a fresh copy of the archived user-contributed data
of the global SHEBANQ will be imported.

## How do I backup and restore the data in my local SHEBANQ?

Make sure that the deployment is running (`./shebanq.sh up`).

Open a shell within the shebanq container of the deployment:

```
./shebanq.sh sh
```

In that shell, run the backup script:

```
cd src/scripts
./backup.sh
exit
```

The backup will be saved in a new `backup` directory at the top-level of your
`shebanq-local` clone. You may want to copy it from their to a different place.

You can restore a backup from the `backup` directory by:

```
./shebanq.sh sh
```

and then

```
cd src/scripts
./restore.sh
exit
```

## How do I export and import data in my local SHEBANQ?

If you want complete control over your data, you can export the data to tab-delimited
files. You can then modify this data at will and reimport it. 

In fact, we used this method to curate the data of the global SHEBANQ into a dataset
that we can distribute freely without violating the privacy of users that contributed
the data.
See the
[curation directory](https://github.com/ETCBC/shebanq-local/tree/master/curation)
and especially the 
[curation notebook](https://github.com/ETCBC/shebanq-local/blob/master/curation/Curate.ipynb)
and the
[auxiliary python curation code](https://github.com/ETCBC/shebanq-local/blob/master/curation/helpers.py).

The data will and up in your `backup` directory, in subdirectories
`shebanq_web` and `shebanq_note`. For each table you'll find two files:

*   *table*`.sql` The definition of the table
*   *table*`.txt` The data of the table in TSV format.

The steps to do export and import are completely analogous to the backup and restore 
steps:

```
./shebanq.sh sh
```

```
cd src/scripts
./export.sh
exit
```

and 

```
./shebanq.sh sh
```

```
cd src/scripts
./import.sh
exit
```

## How can I look directly into the mysql tables of shebanq?

Make sure your `shebanq-local` deployment is up (`./shebanq.sh up`).

If you have a mysqlclient installed on your system, you can open a terminal, go to
the directory of your `shebanq-local` clone, and give this command:

```
./shebanq.sh sql
```

Now you are in a mysql command prompt.

If you do not have a mysqlclient and do not want to install one, you can open
a shell in the shebanqdb container:

```
./shebanq.sh sh db
mysql -u root -p"${MYSQL_ROOT_PASSWORD}"
```

And now you are also in a mysql command prompt.

In that prompt you can, for example, count the number of queries:

```
MariaDB [(none)]> use shebanq_web;
Reading table information for completion of table and column names
You can turn off this feature to get a quicker startup with -A

Database changed
MariaDB [shebanq_web]> select count(*) from query;
+----------+
| count(*) |
+----------+
|     1130 |
+----------+
1 row in set (0.010 sec)

MariaDB [shebanq_web]>exit 
Bye
```

## How can I easily navigate to the relevant SHEBANQ resources?

In your `shebanq-local` directory do

*   `./shebanq.sh browse` to go to your local shebanq website
*   `./shebanq.sh browse admin` to go to the admin interface of the shebanq website
*   `./shebanq.sh browse code` to go to the github repository of `shebanq-local`
*   `./shebanq.sh browse image` to go to the docker hub where the image of
    `shebanq-local` resides

## How can I build a new shebanq image and distribute this?

Obviously, this is relevant for developers only.

After you have made changes to shebanq that imply that a new image must be built,
do the following:

*   increase the dockertag in the `.env` file
*   `./shebanq.sh build` to build a new image locally
*   `./shebanq.sh push` to push the image to docker hub so that it is available to
    others.
