#!/bin/bash
#
# FlockLab2 server update script.

USER="flocklab"
HOST="flocklab-dev-server"

echo "Going to update files on FlockLab server $HOST..."
sleep 2   # give the user time to abort, just in case

# testmanagement server files
RES=$(rsync -a -z -c -i --dry-run --exclude=".git" -e "ssh -q" testmanagementserver/ ${USER}@${HOST}:testmanagementserver/ | grep '^<fc' | cut -d' ' -f2)
if [ -z "$RES" ]; then
    echo "Testmanagement server files are up to date."
else
    printf "Updating testmanagement server files... "
    rsync -a -q -z -c --exclude=".git" -e "ssh -q" testmanagementserver ${USER}@${HOST}:
    if [ $? -ne 0 ]; then
        printf "Failed to copy files!\n"
        continue
    else
        printf "done.\n"
    fi
fi
# webserver files
RES=$(rsync -a -z -c -i --dry-run --exclude=".git" -e "ssh -q" webserver/ ${USER}@${HOST}:webserver/ | grep '^<fc' | cut -d' ' -f2)
if [ -z "$RES" ]; then
    echo "Webserver files are up to date."
else
    printf "Updating webserver files..."
    rsync -a -q -z -c --exclude=".git" -e "ssh -q" webserver ${USER}@${HOST}:
    if [ $? -ne 0 ]; then
        printf "failed to copy repository files!\n"
        continue
    else
        printf "done.\n"
    fi
fi

