CC=gcc
CFLAGS=-Wall -Wextra -Werror -pedantic -O3 -g
SOURCES=$(wildcard *.c)
EXECUTABLES=$(SOURCES:.c=)

all: $(EXECUTABLES)

%: %.c
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -f $(EXECUTABLES)
