from textwrap import dedent
from markdown import markdown

from tf.core.helpers import console, run
from tf.core.files import dirContents, initTree, fileExists, fileCopy, expanduser as ex
from tf.lib import writeSets
from tf.app import use


VERSIONS = ("4", "4b", "2016", "2017", "c", "2021")
VNEXT = {
    "4": "4b",
    "4b": "2016",
    "2016": "2017",
    "2017": "2021",
    "c": "2021",
}


def getLocations(obj, BASEDIR):
    baseDir = ex(BASEDIR)
    obj.baseDir = baseDir
    obj.shebanqDir = f"{baseDir}/ETCBC/shebanq-local"
    obj.bhsaDir = f"{baseDir}/ETCBC/bhsa"
    obj.backupDir = f"{obj.shebanqDir}/backup"
    obj.contentDir = f"{obj.shebanqDir}/content"
    obj.curationDir = f"{obj.shebanqDir}/curation"
    obj.tempDir = f"{obj.shebanqDir}/_temp"
    obj.docsDir = f"{obj.shebanqDir}/docs"
    obj.queryDir = f"{obj.docsDir}/hebrew/query"
    obj.bhsa = "ETCBC/bhsa"


class SQL:
    def __init__(self, BASEDIR, zapTables=set()):
        getLocations(self, BASEDIR)
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

    def writeQResultsTF(self, mappingsFrom):
        data = self.data
        contentDir = self.contentDir

        monadRows = data["shebanq_web"]["monads"]
        queryexeRows = data["shebanq_web"]["query_exe"]

        versionFromQueryexe = {}

        for r in queryexeRows:
            qId, qeId, version = r[10], r[0], r[2]
            versionFromQueryexe[qeId] = (qId, version)

        resultsTF = {}

        for qeId, fromM, toM in monadRows:
            (qId, version) = versionFromQueryexe[qeId]
            is2021 = version == "2021"
            versionRep = "" if is2021 else f"_{version}"

            for i in range(int(fromM), int(toM) + 1):
                resultsTF.setdefault(f"q{qId}{versionRep}", set()).add(
                    i if is2021 else mappingsFrom[version][i]
                )
        writeSets(resultsTF, f"{contentDir}/qresults.tfx")

    def genQueryPages(self):
        def nonNull(x):
            return not (x == "" or x == "\\N")

        def zapNull(x):
            return "" if x == "\\N" else x

        def unesc(x):
            return x.replace("\\n", "\n").replace("\\t", "\t")

        def norm(x):
            return x.replace("'", "").replace('"', "").strip()

        ORIG = "shebanq.ancient-data.org/hebrew/query"
        LOCAL = "localhost:8000/hebrew/query"

        data = self.data
        queryDir = self.queryDir
        curationDir = self.curationDir
        templateFile = f"{curationDir}/template.html"
        indexFile = f"{queryDir}/index.html"
        jsFileSrc = f"{curationDir}/helpers.js"
        jsFileDst = f"{queryDir}/helpers.js"
        cssFileSrc = f"{curationDir}/design.css"
        cssFileDst = f"{queryDir}/design.css"

        console("Cleaning previous results ... ")
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
            projects[projectId] = (name, website if nonNull(website) else "")

        console("Gathering organizations ... ")

        orgs = {}

        for r in orgRows:
            (orgId, name, website) = r[0:3]
            orgs[orgId] = (name, website if nonNull(website) else "")

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

        fields = (
            ("query id", True, False),
            ("text version", True, True),
            ("TF set", True, True),
            ("title", True, True),
            ("creator", True, True),
            ("project", True, True),
            ("organization", True, True),
            ("local shebanq", False, True),
        )

        with open(templateFile) as fh:
            template = fh.read()

        nq = 0
        nqe = 0

        queryTable = []
        queryTable.append("<thead>\n\t<tr>")

        for c, field in enumerate(fields):
            name, sortable, asString = field
            typeRep = "true" if asString else "false"
            sortControls = []

            if sortable:
                for asc in True, False:
                    dRep = "true" if asc else "false"
                    dIcon = "↑" if asc else "↓"
                    sortControls.append(
                        """<a class="button" """
                        f"""onclick="sortTable({c}, {dRep}, {typeRep})">{dIcon}</a>"""
                    )

            queryTable.append(
                f"""<th>{sortControls[0]}{name}{sortControls[1]}</th>\n"""
                if sortable
                else f"""<th>{name}</th>"""
            )

        queryTable.append("</tr>\n<tr>\n")

        for c, field in enumerate(fields):
            name, sortable, asString = field
            filterControl = (
                (
                    """<input class="filter" type="text" """
                    """onkeyup="filterTable()" placeholder="filter ..">"""
                )
                if sortable
                else (
                    """<input class="filter" type="hidden">"""
                )
            )
            queryTable.append(f"""<th>{filterControl}</th>\n""")

        queryTable.append("</tr>\n</thead>\n<tbody>" "")

        for qId in sorted(queries):
            qInfo = queries[qId]
            qMeta = qInfo["meta"]
            qVersions = qInfo["exe"]

            name = qMeta["name"]
            description = qMeta["description"]
            createdBy = qMeta["createdBy"]
            (project, pUrl) = qMeta["project"]
            (organization, oUrl) = qMeta["organization"]
            dateCreated = qMeta["dateCreated"]
            dateModified = qMeta["dateModified"]
            dateShared = qMeta["dateShared"]

            pRep = f"[{project}]({pUrl})" if pUrl else project
            oRep = f"[{organization}]({oUrl})" if oUrl else organization

            metaUrl = f"q{qId}.html"
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
                | *project* | {pRep} |
                | *organization* | {oRep} |
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

                versionRep = "" if version == "2021" else f"-{version}"
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

                tfSet = f"q{qId}{versionRep}"

                origFull = (
                    "http://shebanq.ancient-data.org/hebrew/query?version=4b&id=1780"
                )

                queryTable.append(
                    f"""
                    <tr>
                        <td key="{qId}"><a href="{metaUrl}">{qId}</a></td>
                        <td key="{version}">{version}</td>
                        <td key="{tfSet}">{tfSet}</td>
                        <td key="{norm(name.lower())}">{name}</td>
                        <td key="{createdBy.lower()}">{createdBy}</td>
                        <td key="{project.lower()}"><a href="{pUrl}">{project}</a></td>
                        <td key="{organization.lower()}"><a href="{oUrl}">{organization}</a></td>
                        <td><a href="{localVFull}">url</a></td>
                    </tr>
                    """
                )

                nqe += 1
                md += dedent(
                    f"""\
                    ### {version}

                    | property | value |
                    | --- | --- |
                    | *id* | `{qeId}` |
                    | *TF set* | **`{tfSet}`** |
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

            with open(f"{queryDir}/q{qId}.html", "w") as fh:
                fh.write(markdown(md, extensions=["tables", "fenced_code"]))

        queryTable.append("</tbody>\n")

        with open(indexFile, "w") as fh:
            fh.write(template.replace("{{queryTable}}", "".join(queryTable)))

        fileCopy(jsFileSrc, jsFileDst)
        fileCopy(cssFileSrc, cssFileDst)

        console(f"Generated {nqe} pages for {nq} queries")


class Check:
    def __init__(self, BASEDIR):
        getLocations(self, BASEDIR)

    def unzip(self):
        bhsaDir = self.bhsaDir
        tempDir = self.tempDir

        for version in VERSIONS:
            mqlZipFile = (
                f"{bhsaDir}/bhsa/shebanq/{version}/shebanq_etcbc{version}.mql.bz2"
            )
            mqlFile = f"{tempDir}/shebanq_etcbc{version}.mql"

            if not fileExists(mqlFile):
                console(f"unzipping {mqlZipFile}")
                result = run(f"bunzip2 -k -c {mqlZipFile} > {mqlFile}")

                if not result[0]:
                    console(result[-1], error=True)

    def monads(self):
        tempDir = self.tempDir

        for version in VERSIONS:
            mqlFile = f"{tempDir}/shebanq_etcbc{version}.mql"

            console(f"Checking {version} from {mqlFile}")

            curMonad = 0
            gaps = []

            with open(mqlFile) as fh:
                skip = True

                for ln, line in enumerate(fh):
                    if line == "WITH OBJECT TYPE[word]\n":
                        skip = False

                    if line == "GO\n":
                        skip = True

                    if skip:
                        continue

                    if line.startswith("FROM MONADS"):
                        monad = int(
                            line.split("=", 1)[1]
                            .replace("{", "")
                            .replace("}", "")
                            .strip()
                        )

                        if curMonad + 1 != monad:
                            gaps.append((ln + 1, curMonad, monad))

                        curMonad = monad

            nGaps = len(gaps)

            console(f"\tlast monad = {monad}")
            console(f"\tthere were {nGaps} gaps", error=nGaps > 0)

            for ln, b, e in gaps:
                console(f"\t\tline {ln}: gap from {b} to {e}", error=True)


class Mapper:
    def __init__(self, BASEDIR):
        getLocations(self, BASEDIR)
        A = {}
        self.A = A

    def load(self):
        A = self.A
        baseDir = self.baseDir
        bhsa = self.bhsa

        for v in VERSIONS:
            A[v] = use(
                f"{bhsa}:clone",
                checkout="clone",
                mod=[],
                version=v,
                source=baseDir,
            )

    def unload(self):
        self.A = {}

    def makeMappings(self):
        A = self.A

        self.mappingsFrom = {}
        mappingsFrom = self.mappingsFrom
        self.mappingsGaps = {}
        mappingsGaps = self.mappingsGaps

        for v in reversed(VERSIONS):
            if v == "2021":
                continue

            console(f"map {v}-slots to 2021 slots ...")
            nextV = VNEXT[v]

            mapFeat = f"omap@{v}-{nextV}"
            A[nextV].load(mapFeat)
            smap = A[nextV].api.Es(mapFeat).f
            maxSlot = A[v].api.F.otype.maxSlot

            thisMapping = {}
            theseGaps = {}

            for n in range(1, maxSlot + 1):
                x = smap(n)

                if x:
                    thisMapping[n] = list(x)[0][0]
                else:
                    theseGaps[n] = (v, None)

            if nextV == "2021":
                mappingsFrom[v] = thisMapping
            else:
                remainingMapping = mappingsFrom[nextV]
                mappingsFrom[v] = {}
                fullMapping = mappingsFrom[v]

                for n in range(1, maxSlot + 1):
                    if n in thisMapping:
                        nn = thisMapping[n]

                        if nn in remainingMapping:
                            fullMapping[n] = remainingMapping[nn]
                        else:
                            theseGaps[n] = (nextV, nn)

            mappingsGaps[v] = theseGaps
            nGaps = len(theseGaps)
            console(f"\t{nGaps} gaps")

    def checkGaps(self):
        A = self.A

        mappingsFrom = self.mappingsFrom

        for v in VERSIONS:
            if v == "2021":
                continue

            maxSlot = A[v].api.F.otype.maxSlot

            gaps = 0
            thisMapping = mappingsFrom[v]

            for n in range(1, maxSlot):
                if n not in thisMapping:
                    gaps += 1

            console(f"mapping {v} to 2021 has {gaps} gaps")

    def showValues(self, *nodes):
        mappingsFrom = self.mappingsFrom

        for n in nodes:
            for v in reversed(VERSIONS):
                if v == "2021":
                    continue

                console(f"{v:>4}-slot {n} maps to {mappingsFrom[v][n]}")
            console("")
