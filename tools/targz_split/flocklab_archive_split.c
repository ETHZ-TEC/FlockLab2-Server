/**
 * Copyright (c) 2020, ETH Zurich, Computer Engineering Group
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice, this
 *   list of conditions and the following disclaimer.
 *
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * * Neither the name of the copyright holder nor the names of its
 *   contributors may be used to endorse or promote products derived from
 *   this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 * Author: Reto Da Forno
 */

// intended usage: zcat flocklab_testresults_XXXX.tar.gz | ./flocklab_archive_split | gzip > flocklab_testresults_XXXX_nopower.tar.gz
// note: in order for this to work, the powerprofiling.csv file needs to be the last in the archive
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <regex.h>

char * tarbuf;
static char filename[100];
static int reti, num;
static regex_t regex;

#define TARBUFSIZE 512

int main ( int argc, char *argv[] ) {
    reti = regcomp(&regex, "^[[:digit:]]*/powerprofiling\\.csv$", REG_EXTENDED);
    if (reti!=0) {
        fprintf(stderr, "could not compile regexp. %d\n", reti);
        return 1;
    }
    
    tarbuf = malloc(TARBUFSIZE);
    if (!tarbuf) {
        regfree(&regex);
        fprintf(stderr, "could not allocate memory.\n");
        return 1;
    }

    num = 0;
    while(fread(tarbuf, TARBUFSIZE, 1, stdin)) {
        num++;
        snprintf(filename, sizeof(filename), "%s", tarbuf);
        reti = regexec(&regex, filename, 0, NULL, 0);
        if (reti==0) {
//             fprintf(stderr, "file name: %s %d\n", filename, reti);
            memset(tarbuf, 0, TARBUFSIZE);
            fwrite(tarbuf, TARBUFSIZE, 1, stdout);
            fwrite(tarbuf, TARBUFSIZE, 1, stdout);
            break;
        }
         fwrite(tarbuf, TARBUFSIZE, 1, stdout);
    }
//     fprintf(stderr, "pages read: %d\n", num);

    regfree(&regex);
    free(tarbuf);
    
    return 0;
}
