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
// 			fprintf(stderr, "file name: %s %d\n", filename, reti);
			memset(tarbuf, 0, TARBUFSIZE);
			fwrite(tarbuf, TARBUFSIZE, 1, stdout);
			fwrite(tarbuf, TARBUFSIZE, 1, stdout);
			break;
		}
 		fwrite(tarbuf, TARBUFSIZE, 1, stdout);
	}
// 	fprintf(stderr, "pages read: %d\n", num);

	regfree(&regex);
	free(tarbuf);
	
	return 0;
}
