#!/bin/bash
#
# Copyright (c) 2020, ETH Zurich, Computer Engineering Group
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Author: Reto Da Forno
#

#
# FlockLab2 server update script.
#

USER="flocklab"
HOST="flocklab"    # default server
RSYNCPARAMS="-a -z -c -K --exclude=.* --exclude=*.dat --no-perms --no-owner --no-group --ignore-times --delete"
LOCKFILE="update.lock"    # write '1' into this file (on the server) to prevent this script from updating/overwriting files

if [ $# -gt 0 ]; then
    HOST=$1
fi

echo "Going to update files on FlockLab server $HOST..."
sleep 2   # give the user time to abort, just in case

# simple locking mechanism: before continuing, make sure the lock is released
RES=$(ssh ${USER}@${HOST} "cat ${LOCKFILE}" 2> /dev/null)
if [ $? -eq 0 ] && [ $RES == "1" ]; then
    echo "File system is locked."
    exit 1;
fi

# testmanagement server files
# optional to only look for changed files:  | grep '^<fc' | cut -d' ' -f2
RES=$(rsync ${RSYNCPARAMS} -i --dry-run -e 'ssh -q' testmanagementserver/ ${USER}@${HOST}:testmanagementserver  2>&1)
if [ -z "$RES" ]; then
    echo "Testmanagement server files are up to date."
else
    printf "Updating testmanagement server files... "
    rsync ${RSYNCPARAMS} -e 'ssh -q' testmanagementserver/ ${USER}@${HOST}:testmanagementserver
    if [ $? -ne 0 ]; then
        printf "Failed to copy files!\n"
    else
        printf "done.\n"
    fi
fi
# webserver files
RES=$(rsync ${RSYNCPARAMS} -i --dry-run -e 'ssh -q' webserver/ ${USER}@${HOST}:webserver  2>&1)
if [ -z "$RES" ]; then
    echo "Webserver files are up to date."
else
    printf "Updating webserver files... "
    rsync ${RSYNCPARAMS} -e 'ssh -q' webserver/ ${USER}@${HOST}:webserver
    if [ $? -ne 0 ]; then
        printf "failed to copy repository files!\n"
    else
        printf "done.\n"
    fi
fi
# tools
RES=$(rsync ${RSYNCPARAMS} -i --dry-run -e 'ssh -q' tools/ ${USER}@${HOST}:tools  2>&1)
if [ -z "$RES" ]; then
    echo "Tools are up to date."
else
    printf "Updating tools... "
    rsync ${RSYNCPARAMS} -e 'ssh -q' tools/ ${USER}@${HOST}:tools
    if [ $? -ne 0 ]; then
        printf "Failed to copy files!\n"
    else
        printf "done.\n"
    fi
fi
