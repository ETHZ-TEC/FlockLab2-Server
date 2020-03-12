#!/bin/bash
#
# FlockLab2 server update script.

USER="flocklab"
HOST="flocklab-dev-server"
RSYNCPARAMS="-a -z -c -K --exclude=.git"

if [ $# -gt 0 ]; then
    HOST=$1
fi

echo "Going to update files on FlockLab server $HOST..."
sleep 2   # give the user time to abort, just in case

# testmanagement server files
# optional to only look for changed files:  | grep '^<fc' | cut -d' ' -f2
RES=$(rsync ${RSYNCPARAMS} -i --dry-run -e 'ssh -q' testmanagementserver ${USER}@${HOST}:testmanagementserver)
if [ -z "$RES" ]; then
    echo "Testmanagement server files are up to date."
else
    printf "Updating testmanagement server files... "
    rsync ${RSYNCPARAMS} -e 'ssh -q' testmanagementserver ${USER}@${HOST}:
    if [ $? -ne 0 ]; then
        printf "Failed to copy files!\n"
        continue
    else
        printf "done.\n"
    fi
fi
# webserver files
RES=$(rsync ${RSYNCPARAMS} -i --dry-run -e 'ssh -q' webserver ${USER}@${HOST}:webserver)
if [ -z "$RES" ]; then
    echo "Webserver files are up to date."
else
    printf "Updating webserver files..."
    rsync ${RSYNCPARAMS} -e 'ssh -q' webserver ${USER}@${HOST}:
    if [ $? -ne 0 ]; then
        printf "failed to copy repository files!\n"
        continue
    else
        printf "done.\n"
    fi
fi
# tools
RES=$(rsync ${RSYNCPARAMS} -i --dry-run -e 'ssh -q' tools ${USER}@${HOST}:tools)
if [ -z "$RES" ]; then
    echo "Tools are up to date."
else
    printf "Updating tools... "
    rsync ${RSYNCPARAMS} -e 'ssh -q' tools ${USER}@${HOST}:
    if [ $? -ne 0 ]; then
        printf "Failed to copy files!\n"
        continue
    else
        printf "done.\n"
    fi
fi
