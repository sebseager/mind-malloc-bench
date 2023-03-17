CC=gcc
SOURCE=alloc_test.c
TARGET=alloc_test

all:
	$(CC) $(SOURCE) -o $(TARGET) -I`jemalloc-config --includedir` -L`jemalloc-config --libdir` -Wl,-rpath,`jemalloc-config --libdir` -ljemalloc `jemalloc-config --libs`

clean:
	rm -f $(TARGET)
