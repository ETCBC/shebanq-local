import os
from gluon import current

# from helpers import debug

response.logo = A(
    IMG(_src=URL("static", "images/shebanq_logo_small.png")),
    _class="brand",
    _href=URL("default", "index"),
    _title="Home page",
    _style="margin-bottom: -2em;",
)

response.logo2 = A(
    IMG(_src=URL("static", "images/etcbc-round-small.png")),
    _class="brand",
    _href="http://www.etcbc.nl",
    _title="to the ETCBC website",
    _target="_blank",
    _style="margin-bottom: -2em;",
)

# we get the machine name by inspecting several values
# it is in request.env.SERVER_NAME if we are running in a web server
# But if we run in the web2py shell, we have to inspect the environment
# On macos it is HOST, on Linux it is HOSTNAME
runMode = os.environ.get("runmode", "unknown")

inMaintenance = runMode == "maintenance"
onProd = runMode == "production"
onDev = runMode == "develop"
onOther = not (inMaintenance or onProd or onDev)

current.SITUATION = (
    "production"
    if onProd
    else "develop"
    if onDev
    else "maintenance"
    if inMaintenance
    else "other"
)
current.DEBUG = onDev or inMaintenance


response.title = request.function.replace("_", " ").capitalize()
response.subtitle = ""

# read more at http://dev.w3.org/html5/markup/meta.name.html
response.meta.author = "SHEBANQ <w.t.van.peursen@vu.nl>"
response.meta.description = (
    "Search engine for biblical Hebrew"
    " based on the Biblia Hebraica Stuttgartensia (Amstelodamensis)"
    " database (formerly known as ETCBC, historically known as WIVU)."
    " \nDo not reply to this email address, it will not be read."
    " \nA contact address can be found on https://github.com/ETCBC/shebanq/wiki"
)
response.meta.keywords = (
    "Hebrew, Text Database, Bible, Query, Annotation, Online Hebrew Bible, "
    "Online Bible Hebrew, Hebrew Online Bible, Hebrew Bible Reader, "
    "Hebrew Bible Search, Hebrew Bible Research, Data Science, Text Database, "
    "Linguistic Queries, WIVU, ETCBC, BHS, BHSA, Biblia Hebraica, "
    "Biblia Hebraica Stuttgartensia, Biblia Hebraica Stuttgartensia Amstelodamensis"
)
response.meta.generator = "BHSA Data"

# your http://google.com/analytics id
response.google_analytics_id = None

#########################################################################
# this is the main application menu add/remove items as required
#########################################################################

response.menu = [
    ("" if onProd else current.SITUATION, False, None, []),
    (T("Text"), False, URL("hebrew", "text", vars=dict(mr="m")), []),
    (T("Words"), False, URL("hebrew", "words"), []),
    (T("Queries"), False, URL("hebrew", "queries"), []),
    (T("Notes"), False, URL("hebrew", "notes"), []),
    (
        SPAN(_title="SHEBANQ Wiki", _class="fa fa-info-circle fa-2x"),
        False,
        "https://github.com/ETCBC/shebanq/wiki",
        [],
    ),
]

response.about = "https://github.com/ETCBC/shebanq/wiki"

if "auth" in locals():
    auth.wikimenu()
