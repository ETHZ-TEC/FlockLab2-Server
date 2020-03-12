CFLAGS+=-Wall

all: flocklab_archive_split.c
	gcc ${CFLAGS} -o flocklab_archive_split flocklab_archive_split.c

install: all
	cp flocklab_archive_split ..

clean:
	rm flocklab_archive_split
