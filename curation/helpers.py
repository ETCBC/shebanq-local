from textwrap import dedent
from markdown import markdown

from tf.core.helpers import console
from tf.core.files import dirContents, initTree
from tf.lib import writeSets

VERSIONS = ("4", "4b", "2016", "2017", "c", "2021")


class SQL:
    def __init__(self, backupDir, zapTables=set()):
        self.backupDir = backupDir
        self.zapTables = zapTables
        self.data = {}
        self.readData()

    def readData(self):
        backupDir = self.backupDir
        zapTables = self.zapTables
        data = self.data

        for db in dirContents(backupDir)[1]:
            files = dirContents(f"{backupDir}/{db}")[0]

            tables = set()

            for file in files:
                (table, kind) = file.rsplit(".", 1)

                if kind == "txt":
                    tables.add(table)

                    if tables in zapTables:
                        data.setdefault(db, {})[table] = []
                    else:
                        with open(f"{backupDir}/{db}/{file}") as fh:
                            text = fh.read().strip()

                            if len(text) == 0:
                                rows = []
                            else:
                                text = text.replace("\\\n", "\\n").rstrip()
                                lines = text.split("\n")

                                rows = [
                                    line.replace("\\\t", "\\t").split("\t")
                                    for line in lines
                                ]
                            data.setdefault(db, {})[table] = rows

    def writeData(self):
        backupDir = self.backupDir
        data = self.data

        for db, tables in data.items():
            for table, rows in tables.items():
                with open(f"{backupDir}/{db}/{table}.txt", "w") as fh:
                    newLine = ""

                    for row in rows:
                        fh.write(newLine)
                        if not newLine:
                            newLine = "\n"
                        fh.write(
                            "\t".join(
                                field.replace("\\t", "\\\t").replace("\\n", "\\\n")
                                for field in row
                            )
                        )

    def check(self, db, table):
        data = self.data

        if db not in data:
            console(f"No such database: {db}", error=True)
            return False

        if table is None:
            return True

        tableInfo = data[db]

        if table not in tableInfo:
            console(f"\tNo such table: {table}", error=True)
            return False

        return True

    def stats(self, db=None, table=None):
        data = self.data
        zapTables = self.zapTables

        dbs = sorted(data) if db is None else [db]

        for d in dbs:
            if not self.check(d, None):
                continue

            console(f"Database {d}:")
            tableInfo = data[d]
            tables = sorted(tableInfo) if table is None else [table]

            for t in tables:
                if not self.check(d, t):
                    continue

                if t in zapTables:
                    continue

                rows = tableInfo[t]
                nRows = len(rows)
                console(f"\tTable {t:<25}: {nRows:>8} rows")

    def keep(self, db, table, condition):
        if not self.check(db, table):
            return

        data = self.data
        rows = data[db][table]
        data[db][table] = [r for r in rows if condition(r)]

    def getIds(self, db, table, field):
        if not self.check(db, table):
            return

        data = self.data
        rows = data[db][table]
        return {r[field] for r in rows}

    def trimTable(self, db, table, field, keepIds):
        if not self.check(db, table):
            return

        data = self.data
        rows = data[db][table]
        data[db][table] = [r for r in rows if r[field] in keepIds]

    def trimDetails(self, db, table, detailDb, detailTable, detailField):
        if not self.check(db, table):
            return
        if not self.check(detailDb, detailTable):
            return

        keepIds = self.getIds(db, table, 0)
        self.trimTable(detailDb, detailTable, detailField, keepIds)

    def trimMaster(self, db, table, field, masterDb, masterTable):
        if not self.check(db, table):
            return
        if not self.check(masterDb, masterTable):
            return

        keepIds = self.getIds(db, table, field)
        self.trimTable(masterDb, masterTable, 0, keepIds)

    def zapFields(self, db, table, *fields):
        if not self.check(db, table):
            return

        data = self.data
        rows = data[db][table]

        for r in rows:
            for field in fields:
                r[field] = "\\N"

    def writeQResultsTF(self, mappingsFrom, destDir):
        data = self.data

        monadRows = data["shebanq_web"]["monads"]
        queryexeRows = data["shebanq_web"]["query_exe"]

        versionFromQueryexe = {}

        for r in queryexeRows:
            qeId, version = r[0], r[2]
            versionFromQueryexe[qeId] = version

        resultsTF = {}

        for qeId, fromM, toM in monadRows:
            version = versionFromQueryexe[qeId]
            is2021 = version == "2021"

            for i in range(int(fromM), int(toM) + 1):
                resultsTF.setdefault(f"qe{qeId}", set()).add(
                    i if is2021 else mappingsFrom[version][i]
                )
        writeSets(resultsTF, f"{destDir}/qresults.tfx")

    def genQueryPages(self, docDir):
        def nonNull(x):
            return not (x == "" or x == "\\N")

        def zapNull(x):
            return "" if x == "\\N" else x

        def unesc(x):
            return x.replace("\\n", "\n").replace("\\t", "\t")

        ORIG = "shebanq.ancient-data.org/hebrew/query"
        LOCAL = "localhost:8000/hebrew/query"

        data = self.data

        console("Cleaning previous results ... ")
        queryDir = f"{docDir}/hebrew/query"
        initTree(queryDir, fresh=True, gentle=True)

        userRows = data["shebanq_web"]["auth_user"]
        orgRows = data["shebanq_web"]["organization"]
        projectRows = data["shebanq_web"]["project"]
        queryRows = data["shebanq_web"]["query"]
        queryexeRows = data["shebanq_web"]["query_exe"]

        console("Gathering projects ... ")

        projects = {}

        for r in projectRows:
            (projectId, name, website) = r[0:3]
            projects[projectId] = f"[{name}]({website})" if nonNull(website) else name

        console("Gathering organizations ... ")

        orgs = {}

        for r in orgRows:
            (orgId, name, website) = r[0:3]
            orgs[orgId] = f"[{name}]({website})" if nonNull(website) else name

        console("Gathering users ... ")

        users = {}

        for r in userRows:
            (userId, firstName, lastName) = r[0:3]
            users[userId] = f"{zapNull(firstName)} {zapNull(lastName)}"

        console("Gathering queries ... ")

        queries = {}

        for r in queryRows:
            (
                queryId,
                name,
                description,
                createdOn,
                createdBy,
                modifiedOn,
                sharedOn,
                isShared,
                project,
                organization,
            ) = r[0:10]

            queries[queryId] = dict(
                exe={},
                meta=dict(
                    name=zapNull(name),
                    description=unesc(zapNull(description)),
                    dateCreated=zapNull(createdOn),
                    createdBy=users[createdBy] if nonNull(createdBy) else "",
                    dateModified=zapNull(modifiedOn),
                    dateShared=zapNull(sharedOn),
                    project=projects[project] if nonNull(project) else "",
                    organization=orgs[organization] if nonNull(organization) else "",
                ),
            )

        console("Gathering query executions ... ")

        for r in queryexeRows:
            (
                qeId,
                mql,
                version,
                eversion,
                resultMonads,
                results,
                executedOn,
                modifiedOn,
                isPublished,
                publishedOn,
                queryId,
            ) = r[0:11]

            queries[queryId]["exe"][version] = dict(
                qeId=qeId,
                mql=unesc(zapNull(mql)),
                emdrosVersion=zapNull(eversion),
                resultWords=int(resultMonads) if nonNull(resultMonads) else "??",
                results=int(results) if nonNull(results) else "??",
                dateExecuted=zapNull(executedOn),
                dateModified=zapNull(modifiedOn),
                datePublished=zapNull(publishedOn),
            )

        console("Generating pages ... ")

        nq = 0
        nqe = 0

        for qId in sorted(queries):
            qInfo = queries[qId]
            qMeta = qInfo["meta"]
            qVersions = qInfo["exe"]

            name = qMeta["name"]
            description = qMeta["description"]
            createdBy = qMeta["createdBy"]
            project = qMeta["project"]
            organization = qMeta["organization"]
            dateCreated = qMeta["dateCreated"]
            dateModified = qMeta["dateModified"]
            dateShared = qMeta["dateShared"]

            origShort = f"{ORIG}?id={qId}"
            origFull = f"https://{origShort}"
            localShort = f"{LOCAL}?id={qId}"
            localFull = f"http://{localShort}"

            nq += 1

            md = dedent(
                f"""\
                # {name}

                | property | value |
                | --- | --- |
                | *id* | `{qId}` |
                | *local link* | [{localShort}]({localFull}) |
                | *original link* | [{origShort}]({origFull}) |
                | *created by* | {createdBy} |
                | *project* | {project} |
                | *organization* | {organization} |
                | *date created* | {dateCreated} |
                | *date modified* | {dateModified} |
                | *date shared* | {dateShared} |

                **Description**

                """
            )
            md += description
            md += dedent(
                """\

                ## Versions

                """
            )

            for version in VERSIONS:
                if version not in qVersions:
                    continue

                qeInfo = qVersions[version]
                qeId = qeInfo["qeId"]
                mql = qeInfo["mql"]
                emdrosVersion = qeInfo["emdrosVersion"]
                results = qeInfo["results"]
                resultWords = qeInfo["resultWords"]
                dateExecuted = qeInfo["dateExecuted"]
                dateModified = qeInfo["dateModified"]
                datePublished = qeInfo["datePublished"]

                origVShort = f"{origShort}&version={version}"
                origVFull = f"{origFull}&version={version}"
                localVShort = f"{localShort}&version={version}"
                localVFull = f"{localFull}&version={version}"

                origFull = "http://shebanq.ancient-data.org/hebrew/query?version=4b&id=1780"

                nqe += 1
                md += dedent(
                    f"""\
                    ### {version}

                    | property | value |
                    | --- | --- |
                    | *id* | `{qeId}` |
                    | *TF set* | **`qe{qeId}`** |
                    | *local link* | [{localVShort}]({localVFull}) |
                    | *original link* | [{origVShort}]({origVFull}) |
                    | *results* | **`{results}`** |
                    | *words in results* | **`{resultWords}`** |
                    | *date executed* | {dateExecuted} |
                    | *date modified* | {dateModified} |
                    | *date published* | {datePublished} |
                    | *Emdros version* | {emdrosVersion} |

                    #### Query instruction (mql)

                    ```
                    """
                )
                md += mql
                md += dedent(
                    """\

                    ```

                    """
                )

            with open(f"{queryDir}/{qId}.html", "w") as fh:
                fh.write(markdown(md, extensions=["tables", "fenced_code"]))

        console(f"Generated {nqe} pages for {nq} queries")
