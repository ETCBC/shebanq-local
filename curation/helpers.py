import re
import collections
import pickle
import gzip
from zipfile import ZipFile
from textwrap import dedent
from markdown import markdown

from tf.parameters import PICKLE_PROTOCOL, GZIP_LEVEL
from tf.core.helpers import console, run
from tf.core.files import (
    dirContents,
    initTree,
    fileExists,
    fileCopy,
    expanduser as ex,
    writeJson,
    readJson,
)
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
WORDDB = "shebanq_passage2021"
LEXICON = "lexicon"
WORD_VERSE = "word_verse"
WORDTABLES = {LEXICON, WORD_VERSE}

TRIM_RE = re.compile(r"[\s+]")


def getLocations(obj, BASEDIR):
    baseDir = ex(BASEDIR)
    obj.baseDir = baseDir
    obj.shebanqDir = f"{baseDir}/ETCBC/shebanq-local"
    obj.bhsaDir = f"{baseDir}/ETCBC/bhsa"
    obj.backupDir = f"{obj.shebanqDir}/backup"
    obj.contentDir = f"{obj.shebanqDir}/content"
    obj.gapFile = f"{obj.contentDir}/gaps.json"
    obj.mapPath = f"{obj.contentDir}/mappings.gz"
    obj.curationDir = f"{obj.shebanqDir}/curation"
    obj.tempDir = f"{obj.shebanqDir}/_temp"
    obj.docsDir = f"{obj.shebanqDir}/docs"
    obj.privDir = f"{obj.shebanqDir}/docsPrivate"
    obj.userBaseDir = f"{obj.privDir}/user"
    obj.userEmailFile = f"{obj.privDir}/userEmail.tsv"
    obj.queryDir = f"{obj.docsDir}/hebrew/query"
    obj.wordDir = f"{obj.docsDir}/hebrew/word"
    obj.bhsa = "ETCBC/bhsa"
    obj.qResultsFile = "qresults.tfx"


def htmlEsc(x):
    return (
        x.replace("&amp;", "&")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def nonNull(x):
    return not (x == "" or x == "\\N")


def zapNull(x):
    return "" if x == "\\N" else x


def zapNullBool(x):
    return False if x == "\\N" else x == "T"


def unesc(x):
    return x.replace("\\n", "\n").replace("\\t", "\t")


def norm(x):
    return x.replace("'", "").replace('"', "").strip()


class Check:
    def __init__(self, BASEDIR):
        getLocations(self, BASEDIR)

    def unzip(self, kind="etcbc", version=None):
        bhsaDir = self.bhsaDir
        tempDir = self.tempDir

        versions = VERSIONS if version is None else (version,)
        ext = "mql" if kind == "etcbc" else "sql"
        extz = "bz2" if kind == "etcbc" else "gz"

        for version in versions:
            mqlZipFile = (
                f"{bhsaDir}/shebanq/{version}/shebanq_{kind}{version}.{ext}.{extz}"
            )
            mqlFile = f"{tempDir}/shebanq_etcbc{version}.{ext}"

            if fileExists(mqlFile):
                console(f"already unzipped: {mqlFile}")
            else:
                console(f"unzipping {mqlZipFile}")
                cmd = "bunzip2" if extz == "bz2" else "gunzip"
                result = run(f"{cmd} -k -c {mqlZipFile} > {mqlFile}")

                if not result[0]:
                    console(result[-1], error=True)

    def monads(self, force=False):
        gapFile = self.gapFile
        tempDir = self.tempDir
        allGaps = {}

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

            console(f"\tlast monad = {curMonad}")
            console(f"\tthere were {nGaps} gaps", error=nGaps > 0)

            for ln, b, e in gaps:
                console(f"\t\tline {ln}: gap from {b} to {e}", error=True)

            allGaps[version] = gaps

        writeJson(allGaps, asFile=gapFile)

    def checkMonads(self, force=False):
        gapFile = self.gapFile

        if not force and fileExists(gapFile):
            allGaps = readJson(asFile=gapFile)

            for version in VERSIONS:
                if version in allGaps:
                    gaps = allGaps[version]
                    nGaps = len(gaps)

                    console(f"\t{version:<4}: there were {nGaps} gaps", error=nGaps > 0)

                    for ln, b, e in gaps:
                        console(f"\t\tline {ln}: gap from {b} to {e}", error=True)

            return

        self.unzip()
        self.monads()


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
            if v in {"4", "4b"}:
                console(
                    "RELAX: warnings concerning the feature voc_lex_utf8 are harmless"
                )

    def unload(self):
        self.A = {}

    def readMappings(self):
        mapPath = self.mapPath

        with gzip.open(mapPath, mode="rb") as f:
            self.mappingsFrom = pickle.load(f)

        console(f"Mappings read from {mapPath}")

    def loadMappings(self, force=False):
        mapPath = self.mapPath

        if force or not fileExists(mapPath):
            self.makeMappings()
            self.writeMappings()
        else:
            self.readMappings()

    def writeMappings(self):
        mapPath = self.mapPath
        mappingsFrom = self.mappingsFrom

        with gzip.open(mapPath, mode="wb", compresslevel=GZIP_LEVEL) as f:
            f.write(pickle.dumps(mappingsFrom, protocol=PICKLE_PROTOCOL))

        console(f"Mappings written to {mapPath}")

    def makeMappings(self):
        A = self.A

        if len(A) == 0:
            self.load()

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

        console("Extra check on gaps:")
        self.checkGaps()
        self.unload()

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


class SQL:
    def __init__(self, BASEDIR, M, zapTables=set()):
        getLocations(self, BASEDIR)
        self.M = M
        self.A = None
        self.zapTables = zapTables
        self.data = {}
        self.readData()
        self.stats()

    def readData(self):
        backupDir = self.backupDir
        zapTables = self.zapTables
        data = self.data

        for db in dirContents(backupDir)[1]:
            files = dirContents(f"{backupDir}/{db}")[0]

            tables = set()

            for file in files:
                table, kind = file.rsplit(".", 1)
                if db == WORDDB and table not in WORDTABLES:
                    continue

                if kind == "txt":
                    tables.add(table)

                    if table in zapTables:
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

        initTree(backupDir, fresh=False)

        for db, tables in data.items():
            if db == WORDDB:
                continue

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

    def load(self):
        baseDir = self.baseDir
        bhsa = self.bhsa
        v = "2021"
        self.A = use(
            f"{bhsa}:clone",
            checkout="clone",
            mod=[],
            version=v,
            source=baseDir,
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
            tables = (
                (sorted(WORDTABLES) if db == WORDDB else sorted(tableInfo))
                if table is None
                else [table]
            )

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

    def getIds(self, db, table, field, condition=None):
        if not self.check(db, table):
            return

        data = self.data
        rows = data[db][table]
        return (
            {r[field] for r in rows}
            if condition is None
            else {r[field] for r in rows if condition(r)}
        )

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

    def reduceToPublic(self):
        self.keep("shebanq_web", "query_exe", lambda r: r[8] == "T")
        self.keep("shebanq_note", "note", lambda r: r[9] == "T" or r[11] == "T")
        self.trimDetails("shebanq_web", "query_exe", "shebanq_web", "monads", 0)
        self.trimMaster("shebanq_web", "query_exe", 10, "shebanq_web", "query")
        self.trimMaster("shebanq_web", "query", 9, "shebanq_web", "organization")
        self.trimMaster("shebanq_web", "query", 8, "shebanq_web", "project")
        userIds = (
            self.getIds("shebanq_web", "query", 4)
            | self.getIds("shebanq_note", "note", 6)
            | self.getIds("shebanq_web", "uploaders", 0)
        )
        self.trimTable("shebanq_web", "auth_user", 0, userIds)
        self.trimTable("shebanq_web", "auth_membership", 1, userIds)
        self.trimMaster(
            "shebanq_web", "auth_membership", 1, "shebanq_web", "auth_group"
        )
        self.zapFields("shebanq_web", "auth_user", 3, 4, 5, 6, 7)
        self.writeData()
        self.stats()

    def writeQResultsTF(self, destPath=None, qIds=None, qeIds=None):
        mappingsFrom = self.M.mappingsFrom
        data = self.data
        contentDir = self.contentDir
        qResultsFile = self.qResultsFile

        monadRows = data["shebanq_web"]["monads"]
        queryexeRows = data["shebanq_web"]["query_exe"]

        versionFromQueryexe = {}

        for r in queryexeRows:
            qId, qeId, version = r[10], r[0], r[2]

            if qIds is not None and qId not in qIds:
                continue

            versionFromQueryexe[qeId] = (qId, version)

        resultsTF = {}
        self.resultsTF = resultsTF

        for qeId, fromM, toM in monadRows:
            if qeIds is not None and qeId not in qeIds:
                continue

            qId, version = versionFromQueryexe[qeId]
            is2021 = version == "2021"
            versionRep = "" if is2021 else f"_{version}"

            for i in range(int(fromM), int(toM) + 1):
                resultsTF.setdefault(f"q{qId}{versionRep}", set()).add(
                    i if is2021 else mappingsFrom[version][i]
                )
        if destPath is None:
            destPath = f"{contentDir}/{qResultsFile}"

        writeSets(resultsTF, destPath)

    def genPrivateQueryPages(self, indexOnly=False):
        data = self.data
        userBaseDir = self.userBaseDir
        userEmailFile = self.userEmailFile

        userRows = data["shebanq_web"]["auth_user"]
        orgRows = data["shebanq_web"]["organization"]
        projectRows = data["shebanq_web"]["project"]
        queryRows = data["shebanq_web"]["query"]
        queryexeRows = data["shebanq_web"]["query_exe"]

        users = {}
        userEmail = {}

        for r in userRows:
            userId, firstName, lastName = r[0:3]
            userName = TRIM_RE.sub(
                " ", f"{zapNull(firstName)} {zapNull(lastName)}".strip()
            )

            if len(userName) > 50:
                continue

            users.setdefault(userName, []).append(r)

        nUsers = len(users)

        if indexOnly:
            initTree(userBaseDir, fresh=False)
        else:
            console("Cleaning previous results ... ")
            initTree(userBaseDir, fresh=True, gentle=False)

        if not indexOnly:
            console(f"Curating queries for {nUsers} users")

        i = 0
        j = 0

        for userName in sorted(users, key=lambda x: x.lower()):
            i += 1
            j += 1

            if j == 10:
                j = 0
                console(
                    f"\r{i:>4} of {nUsers} users: {userName[0:25]:<25}", newline=False
                )

            uRows = users[userName]
            uIds = {r[0] for r in uRows}
            qRows = [r for r in queryRows if r[4] in uIds]
            qIds = {r[0] for r in qRows}
            qeRows = [r for r in queryexeRows if r[10] in qIds]
            qeIds = {r[0] for r in qeRows}
            pIds = {r[8] for r in qRows}
            oIds = {r[9] for r in qRows}

            projects = {}

            for r in projectRows:
                if r[0] not in pIds:
                    continue

                projectId, name, website = r[0:3]
                projects[projectId] = (name, website if nonNull(website) else "")

            orgs = {}

            for r in orgRows:
                if r[0] not in oIds:
                    continue

                orgId, name, website = r[0:3]
                orgs[orgId] = (name, website if nonNull(website) else "")

            self.genUserQueryPages(
                userName,
                uIds,
                uRows,
                qIds,
                qRows,
                qeIds,
                qeRows,
                projects,
                orgs,
                userEmail,
                indexOnly=indexOnly,
            )

        with open(userEmailFile, "w") as fh:
            for email, name in sorted(
                userEmail.items(), key=lambda x: (x[1].lower(), x[0])
            ):
                fh.write(f"{name}\t{email}\n")

        console(f"\r{nUsers} users done                     \n")

    def genUserQueryPages(
        self,
        userName,
        uIds,
        uRows,
        qIds,
        qRows,
        qeIds,
        qeRows,
        projects,
        orgs,
        userEmail,
        indexOnly=False,
    ):
        ORIG = "shebanq.ancient-data.org/hebrew/query"
        LOCAL = "localhost:8000/hebrew/query"

        nameRep = userName.replace(" ", "-")
        userBaseDir = self.userBaseDir
        userZip = f"{userBaseDir}/{nameRep}.zip"
        curationDir = self.curationDir
        templateFileUser = f"{curationDir}/template-user.html"
        templateFileSingle = f"{curationDir}/template-query.html"
        indexFile = "index.html"
        jsFileSrc = f"{curationDir}/helpers.js"
        jsFile = "helpers.js"
        cssFileSrc = f"{curationDir}/design.css"
        cssFile = "design.css"
        qResultsFile = self.qResultsFile

        z = 0

        if not indexOnly:
            while fileExists(userZip):
                z += 1
                userZip = f"{userBaseDir}/{nameRep}-{z}.zip"

        uidRep = ",".join(uIds)
        emails = [zapNull(r[3]) for r in uRows]
        email = ", ".join(emails)

        for e in emails:
            userEmail[e] = nameRep

        if indexOnly:
            return

        userInfo = dedent(f"""\
            # {userName}

            | property | value |
            | --- | --- |
            | *id* | `{uidRep}` |
            | *name* | {userName} |
            | *email* | {email} |

            """)

        queries = {}

        for r in qRows:
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
                    createdBy=userName,
                    dateModified=zapNull(modifiedOn),
                    isShared=zapNullBool(isShared),
                    dateShared=zapNull(sharedOn),
                    project=projects[project] if nonNull(project) else "",
                    organization=orgs[organization] if nonNull(organization) else "",
                ),
            )

        for r in qeRows:
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
                isPublished=zapNullBool(isPublished),
                datePublished=zapNull(publishedOn),
            )

        fields = (
            ("query id", True, False),
            ("text version", True, True),
            ("is published", True, True),
            ("TF set", True, True),
            ("title", True, True),
            ("project", True, True),
            ("organization", True, True),
            ("local shebanq", False, True),
        )

        with open(templateFileUser) as fh:
            templateUser = fh.read()

        with open(templateFileSingle) as fh:
            templateSingle = fh.read()

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
                else ("""<input class="filter" type="hidden">""")
            )
            queryTable.append(f"""<th>{filterControl}</th>\n""")

        queryTable.append("</tr>\n</thead>\n<tbody>" "")

        qFiles = {}

        for qId in sorted(queries):
            qInfo = queries[qId]
            qMeta = qInfo["meta"]
            qVersions = qInfo["exe"]

            name = qMeta["name"]
            nameH = htmlEsc(name)
            description = qMeta["description"]
            createdBy = qMeta["createdBy"]
            project, pUrl = qMeta["project"]
            organization, oUrl = qMeta["organization"]
            dateCreated = qMeta["dateCreated"]
            dateModified = qMeta["dateModified"]
            isShared = qMeta["isShared"]
            dateShared = qMeta["dateShared"]
            isSharedRep = "yes" if isShared else "no"

            pRep = f"[{project}]({pUrl})" if pUrl else project
            oRep = f"[{organization}]({oUrl})" if oUrl else organization

            metaUrl = f"q{qId}.html"
            origShort = f"{ORIG}?id={qId}"
            origFull = f"https://{origShort}"
            localShort = f"{LOCAL}?id={qId}"
            localFull = f"http://{localShort}"

            origLink = f"[{origShort}]({origFull})" if isShared else ""
            localLink = f"[{localShort}]({localFull})" if isShared else ""

            nq += 1

            md = dedent(f"""\
                # {name}

                | property | value |
                | --- | --- |
                | *id* | `{qId}` |
                | *local link* | {origLink} |
                | *original link* | {localLink} |
                | *created by* | {createdBy} |
                | *project* | {pRep} |
                | *organization* | {oRep} |
                | *date created* | {dateCreated} |
                | *date modified* | {dateModified} |
                | *is shared* | {isSharedRep} |
                | *date shared* | {dateShared} |

                **Description**

                """)
            md += description
            md += dedent("""\

                ## Versions

                """)

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
                isPublished = qeInfo["isPublished"]
                datePublished = qeInfo["datePublished"]
                isPubRep = "yes" if isPublished else "no"

                origVShort = f"{origShort}&version={version}"
                origVFull = f"{origFull}&version={version}"
                localVShort = f"{localShort}&version={version}"
                localVFull = f"{localFull}&version={version}"

                origLink = f"[{origVShort}]({origVFull})" if isPublished else ""
                localLink = f"[{localVShort}]({localVFull})" if isPublished else ""
                localLinkIndex = (
                    f'<a href="{localVFull}">url</a>' if isPublished else "&nbsp;"
                )

                tfSet = f"q{qId}{versionRep}"

                queryTable.append(f"""
                    <tr>
                        <td key="{qId}"><a href="{metaUrl}">{qId}</a></td>
                        <td key="{version}">{version}</td>
                        <td key="{isPubRep}">{isPubRep}</td>
                        <td key="{tfSet}">{tfSet}</td>
                        <td key="{norm(nameH.lower())}">{nameH}</td>
                        <td key="{project.lower()}"><a href="{pUrl}">{project}</a></td>
                        <td key="{organization.lower()}"><a href="{oUrl}">{organization}</a></td>
                        <td>{localLinkIndex}</td>
                    </tr>
                    """)

                nqe += 1
                md += dedent(f"""\
                    ### {version}

                    | property | value |
                    | --- | --- |
                    | *id* | `{qeId}` |
                    | *TF set* | **`{tfSet}`** |
                    | *local link* | {localLink} |
                    | *original link* | {origLink} |
                    | *results* | **`{results}`** |
                    | *words in results* | **`{resultWords}`** |
                    | *date executed* | {dateExecuted} |
                    | *date modified* | {dateModified} |
                    | *is published* | {isPubRep} |
                    | *date published* | {datePublished} |
                    | *Emdros version* | {emdrosVersion} |

                    #### Query instruction (mql)

                    ```
                    """)
                md += mql
                md += dedent("""\

                    ```

                    """)

            qFiles[f"q{qId}.html"] = templateSingle.replace(
                "{{name}}", f"{qId} - {nameH}"
            ).replace("{{item}}", markdown(md, extensions=["tables", "fenced_code"]))

        queryTable.append("</tbody>\n")

        qFiles[indexFile] = (
            templateUser.replace("{{name}}", f"{uidRep} - {userName}")
            .replace(
                "{{userInfo}}",
                markdown(userInfo, extensions=["tables", "fenced_code"]),
            )
            .replace("{{itemTable}}", "".join(queryTable))
        )
        qResultsPath = f"{userBaseDir}/{qResultsFile}"
        self.writeQResultsTF(destPath=qResultsPath, qIds=qIds, qeIds=qeIds)

        with ZipFile(userZip, "w") as zf:
            for file, contents in qFiles.items():
                zf.writestr(file, contents)

            for src, dst in (
                (jsFileSrc, jsFile),
                (cssFileSrc, cssFile),
                (qResultsPath, qResultsFile),
            ):
                zf.write(src, arcname=dst)

    def genPublicQueryPages(self):
        ORIG = "shebanq.ancient-data.org/hebrew/query"
        LOCAL = "localhost:8000/hebrew/query"

        data = self.data
        queryDir = self.queryDir
        curationDir = self.curationDir
        templateFile = f"{curationDir}/template-queries.html"
        templateFileSingle = f"{curationDir}/template-query.html"
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
            projectId, name, website = r[0:3]
            projects[projectId] = (name, website if nonNull(website) else "")

        console("Gathering organizations ... ")

        orgs = {}

        for r in orgRows:
            orgId, name, website = r[0:3]
            orgs[orgId] = (name, website if nonNull(website) else "")

        console("Gathering users ... ")

        users = {}

        for r in userRows:
            userId, firstName, lastName = r[0:3]
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

        with open(templateFileSingle) as fh:
            templateSingle = fh.read()

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
                else ("""<input class="filter" type="hidden">""")
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
            project, pUrl = qMeta["project"]
            organization, oUrl = qMeta["organization"]
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

            md = dedent(f"""\
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

                """)
            md += description
            md += dedent("""\

                ## Versions

                """)

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
                nameH = htmlEsc(name)

                queryTable.append(f"""
                    <tr>
                        <td key="{qId}"><a href="{metaUrl}">{qId}</a></td>
                        <td key="{version}">{version}</td>
                        <td key="{tfSet}">{tfSet}</td>
                        <td key="{norm(nameH.lower())}">{nameH}</td>
                        <td key="{createdBy.lower()}">{createdBy}</td>
                        <td key="{project.lower()}"><a href="{pUrl}">{project}</a></td>
                        <td key="{organization.lower()}"><a href="{oUrl}">{organization}</a></td>
                        <td><a href="{localVFull}">url</a></td>
                    </tr>
                    """)

                nqe += 1
                md += dedent(f"""\
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
                    """)
                md += mql
                md += dedent("""\

                    ```

                    """)

            with open(f"{queryDir}/q{qId}.html", "w") as fh:
                fh.write(
                    templateSingle.replace("{{name}}", f"{tfSet} - {nameH}").replace(
                        "{{item}}", markdown(md, extensions=["tables", "fenced_code"])
                    )
                )

        queryTable.append("</tbody>\n")

        with open(indexFile, "w") as fh:
            fh.write(template.replace("{{itemTable}}", "".join(queryTable)))

        fileCopy(jsFileSrc, jsFileDst)
        fileCopy(cssFileSrc, cssFileDst)

        console(f"Generated {nqe} pages for {nq} queries")

    def genWordPages(self, force=False):
        ORIG = "shebanq.ancient-data.org/hebrew/word"
        LOCAL = "localhost:8000/hebrew/word"

        data = self.data
        wordDir = self.wordDir
        reportFile = f"{wordDir}/__README__.txt"
        report = []

        def writeReportFile():
            with open(reportFile, "w") as fh:
                for kind, msg in report:
                    fh.write(f"{kind}\t{msg}\n")

        def readReportFile():
            with open(reportFile) as fh:
                for line in fh:
                    line = line.rstrip()
                    kind, msg = line.split("\t")
                    console(msg, error=kind == "E")

        if not force and fileExists(reportFile):
            readReportFile()
            return

        curationDir = self.curationDir
        templateFile = f"{curationDir}/template-words.html"
        templateFileSingle = f"{curationDir}/template-word.html"
        indexFile = f"{wordDir}/index.html"
        jsFileSrc = f"{curationDir}/helpers.js"
        jsFileDst = f"{wordDir}/helpers.js"
        cssFileSrc = f"{curationDir}/design.css"
        cssFileDst = f"{wordDir}/design.css"

        console("Cleaning previous results ... ")
        initTree(wordDir, fresh=True, gentle=False)

        console("Counting lexemes ...")

        wordVerseRows = data[WORDDB][WORD_VERSE]
        freqOccs = collections.Counter()
        freqVerses = collections.defaultdict(set)

        for r in wordVerseRows:
            verseId, lexId = r[1:3]
            freqOccs[lexId] += 1
            freqVerses[lexId].add(verseId)

        freqV = {lexId: len(verses) for (lexId, verses) in freqVerses.items()}

        console("Gathering lexemes ... ")

        lexRows = data[WORDDB][LEXICON]
        lexemes = {}

        for r in lexRows:
            (
                lexId,
                lan,
                entryId,
                entry,
                entryHeb,
                entryIdHeb,
                gEntry,
                gEntryHeb,
                root,
                pos,
                nametype,
                subpos,
                gloss,
            ) = r[0:13]

            lexemes[lexId] = dict(
                meta=dict(
                    vocalized=zapNull(gEntryHeb),
                    consonantal=zapNull(entryHeb),
                    disambiguated=zapNull(entryIdHeb),
                    vocalizedTrans=unesc(zapNull(gEntry)),
                    consonantalTrans=unesc(zapNull(entry)),
                    disambiguatedTrans=unesc(zapNull(entryId)),
                    partOfSpeech=zapNull(pos),
                    lexicalSet=zapNull(subpos),
                    properNounCategory=zapNull(nametype),
                    language=zapNull(lan),
                    gloss=zapNull(gloss),
                    frequency=freqOccs[lexId],
                    verses=freqV[lexId],
                ),
            )

        nLexemes = len(lexemes)
        console("Generating pages for lexemes ... ")
        report.append(("I", f"There are {nLexemes} lexemes"))

        fields = (
            ("lexId", "lexeme id", True, True),
            ("disambiguatedTrans", "disambiguated (trans)", True, True),
            ("vocalized", "vocalized", True, True),
            ("partOfSpeech", "part of speech", True, True),
            ("lexicalSet", "lexical set", True, True),
            ("properNounCategory", "proper noun category", True, True),
            ("language", "language", True, True),
            ("gloss", "gloss", True, True),
            ("frequency", "frequency", True, False),
            ("local shebanq", "local shebanq", False, True),
        )

        with open(templateFile) as fh:
            template = fh.read()

        with open(templateFileSingle) as fh:
            templateSingle = fh.read()

        lexemeTable = []
        lexemeTable.append("<thead>\n\t<tr>")

        for c, field in enumerate(fields):
            name, nameRep, sortable, asString = field
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

            lexemeTable.append(
                f"""<th>{sortControls[0]}{nameRep}{sortControls[1]}</th>\n"""
                if sortable
                else f"""<th>{nameRep}</th>"""
            )

        lexemeTable.append("</tr>\n<tr>\n")

        for c, field in enumerate(fields):
            name, nameRep, sortable, asString = field
            filterControl = (
                (
                    """<input class="filter" type="text" """
                    """onkeyup="filterTable()" placeholder="filter ..">"""
                )
                if sortable
                else ("""<input class="filter" type="hidden">""")
            )
            lexemeTable.append(f"""<th>{filterControl}</th>\n""")

        lexemeTable.append("</tr>\n</thead>\n<tbody>" "")

        seen = set()

        for lexId in sorted(lexemes, key=lambda x: lexemes[x]["meta"]["disambiguated"]):
            lexLower = lexId.lower()

            if lexLower in seen:
                lexIdF = f"{lexId}-"
                report.append(("E", f"File name clash {lexId}: becomes {lexIdF}"))
            else:
                lexIdF = lexId
                seen.add(lexLower)

            lexInfo = lexemes[lexId]
            lexMeta = lexInfo["meta"]

            vocalized = lexMeta["vocalized"]
            vocalizedTrans = lexMeta["vocalizedTrans"]
            consonantal = lexMeta["consonantal"]
            consonantalTrans = lexMeta["consonantalTrans"]
            disambiguated = lexMeta["disambiguated"]
            disambiguatedTrans = lexMeta["disambiguatedTrans"]
            gloss = lexMeta["gloss"]
            language = lexMeta["language"]
            partOfSpeech = lexMeta["partOfSpeech"]
            lexicalSet = lexMeta["lexicalSet"]
            properNounCategory = lexMeta["properNounCategory"]
            frequency = lexMeta["frequency"]
            verses = lexMeta["verses"]

            fPl = "" if frequency == 1 else "s"
            vPl = "" if verses == 1 else "s"

            metaUrl = f"w{lexIdF}.html"
            origShort = f"{ORIG}?id={lexId}&version={VERSIONS[-1]}"
            origFull = f"https://{origShort}"
            localShort = f"{LOCAL}?id={lexId}&version={VERSIONS[-1]}"
            localFull = f"http://{localShort}"

            disambiguatedTransH = htmlEsc(disambiguatedTrans)
            glossH = htmlEsc(gloss)

            lexemeTable.append(f"""
                <tr>
                    <td key="{lexId}"><a href="{metaUrl}">{lexId}</a></td>
                    <td key="{disambiguatedTransH}">{disambiguatedTransH}</td>
                    <td key="{vocalized}">{vocalized}</td>
                    <td key="{partOfSpeech}">{partOfSpeech}</td>
                    <td key="{lexicalSet}">{lexicalSet}</td>
                    <td key="{properNounCategory}">{properNounCategory}</td>
                    <td key="{language}">{language}</td>
                    <td key="{glossH}">{glossH}</td>
                    <td key="{frequency}">{frequency}</td>
                    <td><a href="{localFull}">url</a></td>
                </tr>
                """)

            md = dedent(f"""\
                # {lexId} - {disambiguatedTrans} - {language} - {gloss}
                # {disambiguated}

                Occurs {frequency} time{fPl} in {verses} verse{vPl}.

                | property | value |
                | --- | --- |
                | *local link* | [{localShort}]({localFull}) |
                | *original link* | [{origShort}]({origFull}) |
                | *consonantal* | {consonantal} |
                | *consonantal (trans)* | `{consonantalTrans}` |
                | *vocalized* | {vocalized} |
                | *vocalized (trans)* | `{vocalizedTrans}` |
                | *part of speech* | `{partOfSpeech}` |
                | *lexical set* | `{lexicalSet}` |
                | *proper noun category* | `{properNounCategory}` |

                """)

            wordFile = f"w{lexIdF}.html"
            wordPath = f"{wordDir}/{wordFile}"

            with open(wordPath, "w") as fh:
                fh.write(
                    templateSingle.replace(
                        "{{name}}", f"{lexId} - {vocalized}"
                    ).replace(
                        "{{item}}", markdown(md, extensions=["tables", "fenced_code"])
                    )
                )

        lexemeTable.append("</tbody>\n")

        with open(indexFile, "w") as fh:
            fh.write(template.replace("{{itemTable}}", "".join(lexemeTable)))

        fileCopy(jsFileSrc, jsFileDst)
        fileCopy(cssFileSrc, cssFileDst)

        nPages = len(dirContents(wordDir)[0])
        nExtra = 4
        nLexPages = nPages - (nExtra - 1)
        # the -1 is for the report file which does not yet exist

        if nLexPages != nLexemes:
            report.append(
                (
                    "E",
                    f"Mismatch between number of lexemes ({nLexemes}) and "
                    f"number of lexeme pages ({nLexPages})",
                )
            )
        else:
            report.append(
                (
                    "I",
                    f"Generated {nLexPages} word pages "
                    f"plus {nExtra} additional files in {wordDir}",
                )
            )

        writeReportFile()
        readReportFile()
