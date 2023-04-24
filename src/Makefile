CC=gcc
CFLAGS=-Wall -Wextra -Werror -pedantic -g
NOBUILTIN=-fno-builtin-malloc -fno-builtin-calloc -fno-builtin-realloc -fno-builtin-free
SOURCE=memtest.c
EXECUTABLE=memtest
SCRIPT_DIR=$(shell pwd)
INSTALL_DIR=$(SCRIPT_DIR)/__tmp_alloc_install/

ptmalloc:
	$(CC) $(CFLAGS) -o $(EXECUTABLE) $(SOURCE)

jemalloc:
	$(CC) $(CFLAGS) -o $(EXECUTABLE) $(SOURCE) -L$(INSTALL_DIR)/jemalloc/lib/ -ljemalloc $(NOBUILTIN)

hoard:
	$(CC) $(CFLAGS) -o $(EXECUTABLE) $(SOURCE) -L$(INSTALL_DIR)/hoard/src/ -Wl,-R$(INSTALL_DIR)/hoard/src/ -lhoard $(NOBUILTIN)

tcmalloc:
	$(CC) $(CFLAGS) -o $(EXECUTABLE) $(SOURCE) -ltcmalloc_minimal $(NOBUILTIN)

clean:
	rm -f $(EXECUTABLE)
