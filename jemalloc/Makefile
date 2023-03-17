CC=gcc
SOURCE=mtest.c
TARGET=mtest

all:
	$(CC) $(SOURCE) -o $(TARGET) -I`jemalloc-config --includedir` -L`jemalloc-config --libdir` -Wl,-rpath,`jemalloc-config --libdir` -ljemalloc `jemalloc-config --libs`

clean:
	rm -f $(TARGET)
