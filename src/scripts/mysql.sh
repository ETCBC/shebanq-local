#!/bin/bash

# Script to run mysql on the server
# Run it on the server.

USAGE="
Usage: ./mysql.sh

Starts the interactive mysql prompt with the right credentials.
"

mcfg="/app/run/cfg/mysql.opt"

mysql --defaults-extra-file="$mcfg"
