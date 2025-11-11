# SHEBANQ

[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.7234733.svg)](https://doi.org/10.5281/zenodo.7234733)
[![SWH](https://archive.softwareheritage.org/badge/origin/https://gitlab.huc.knaw.nl/shebanq/hebrewbible.git/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https://gitlab.huc.knaw.nl/shebanq/hebrewbible.git)

![shebanq](/src/shebanq/static/images/shebanq_logo_small.png)
![tf](/src/shebanq/static/images/tf-small.png)
[![etcbc](src/shebanq/static/images/etcbc-small.png)](https://github.com/ETCBC)
[![huc](src/shebanq/static/images/huc-small.png)](https://di.huc.knaw.nl/text-analysis-en.html)

## About

*System for HEBrew Text: ANnotations for Queries and Markup*

[SHEBANQ](https://shebanq.ancient-data.org)
is a website with a search engine for the Hebrew Bible, powered by the
[BHSA](https://github.com/ETCBC/bhsa)
linguistic database, also known as ETCBC or WIVU.

The ETCBC is lead by
[prof. dr. Willem Th. van Peursen](https://research.vu.nl/en/persons/willem-van-peursen).

## History

SHEBANQ was first deployed in 2014, by DANS, for the ETCBC, in the context of CLARIN.

The evolution of SHEBANQ till now can be seen in
[ETCBC/shebanq](https://github.com/ETCBC/shebanq)
which reflects the history of SHEBANQ since October 2017.
It still contains the documentation and lots of useful information.

As of 2023-12-21 SHEBANQ migrated to KNAW/HuC in the context of CLARIAH,
which acts as the successor of CLARIN.

## Deployment

The deployment is now via *docker* and everything needed to deploy SHEBANQ
can be found in this repository.

**You can have your own shebanq!**

Just install the Docker app, clone this repo, copy `env_template` to `.env`,
and give the command:

```
docker compose up -d
```

See [USAGE](USAGE.md) for the ins and outs of this deployment.

SHEBANQ as seen on
[shebanq.ancient-data.org](https://shebanq.ancient-data.org)
is deployed by
[KNAW/HuC](https://di.huc.knaw.nl/infrastructure-services-en.html).
with configurations in
[behind a firewall](https://code.huc.knaw.nl/tt/shebanq).

# Author

[Dirk Roorda](https://github.com/dirkroorda), working at
[KNAW Humanities Cluster - Digital Infrastructure](https://di.huc.knaw.nl/text-analysis-en.html).

See [team](https://github.com/ETCBC/shebanq/wiki/Team) for a list of people
that have contributed in various ways to the existence of the website SHEBANQ.

Big thanks to my colleagues for making this deployment work:

*   Vic (QiQing) Ding (for navigating through the K8S landscape)
*   Dorian Harmans (for connecting the final dots)
