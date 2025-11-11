HELP="

Run local shebanq

USAGE

./shebanq.sh [up|down||browse|sh|sql|build|push] args

Commands:

up              - start shebanq (press Ctrl-C twice to stop
down            - stop shebanq (mostly not needed)
browse          - go to local shebanq website
browse admin    - go to local shebanq admin website
browse code     - go to github repo of the source code
browse image    - go to docker hub repo of the image (for developers)
sh              - open a shell in the shebanq server
sh db           - open a shell in the mariadb server
sql             - open mysql to operate on the shebanq databases
build           - build the shebanq docker image (for developers)
pull            - pull all missing images for shebanq
push            - push the shebanq docker image (for developers)
"

dockerlocation=droorda/shebanq

function appup {
    # start shebanq, including its services
    export runmode=production
    docker compose up -d "$@"
    docker compose logs -f
    docker compose down
}

function appdown {
    # stop shebanq, including its services (mongod)
    # mostly not needed, because we end appup with Ctrl+C
    docker compose down
}


function appbrowse {
    source .env
    if [[ "$1" == "" ]]; then
        echo open http://localhost:$hostport
        open http://localhost:$hostport
    elif [[ "$1" == "admin" ]]; then
        echo open http://localhost:$hostport/appadmin
        open http://localhost:$hostport/appadmin
    elif [[ "$1" == "code" ]]; then
        echo "open https://github.com/ETCBC/shebanq-local"
        open https://github.com/ETCBC/shebanq-local
    elif [[ "$1" == "image" ]]; then
        echo "open https://hub.docker.com/repository/docker/$dockerlocation/general"
        open https://hub.docker.com/repository/docker/$dockerlocation/general
    else
        echo "Unknown parameter $1"
        echo "Omit it or choose local|code"
    fi
}

function appsh {
    # shell into the running shebanq locally
    if [[ "$1" == "db" ]]; then
        container=shebanqdb
    else
        container=shebanq
    fi
    docker exec -e COLUMNS="`tput cols`" -e LINES="`tput lines`" -it $container /bin/bash -l
}

function appsql {
    # open the host mysql client and connect to the mysql service of shebanq
    source .env
    port=3306

    mysql -h 127.0.0.1 -u root -p"${mysqlrootpwd}" 
}

function appbuild {
    # build the shebanq image
    source .env
    echo "building shebanq docker images from local folder; tagging as docker shebanq:${dockertag}...."
    docker build -f Dockerfile -t shebanq:${dockertag} .

    if [ "$?" == "0" ]; then
      echo "docker images completed ...."
      docker images | grep shebanq:${dockertag}
    else
      echo "docker image building failed!"
      exit 1
    fi
}

function apppull {
    # pull mariadb image if not yet locally present
    source .env
    echo "pull missing images"
    docker compose pull --policy missing db
}

function apppush {
    # push the shebanq image
    source .env
    echo "pushing shebanq docker images to registry $dockerlocation"
    echo "Tip: to see the image online do ./shebanq.sh browse image"

    docker login
    docker tag shebanq:${dockertag} $dockerlocation:${dockertag}
    docker push $dockerlocation:${dockertag}
}

command="$1"

if [[ -z "$1" ]]; then
    echo "no command given"
    printf "$HELP"
fi

command="$1"
shift

app$command "$@"
