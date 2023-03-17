#include <jemalloc/jemalloc.h>
#include <stdlib.h>

#define BASE_ARR_LEN (1024 * 1024)
#define N_ARRS (100)

int *arrays[N_ARRS] = {0};

int *alloc_array(size_t len) { return malloc(len * sizeof(int)); }

void run() {
  // allocate a bunch of arrays
  for (size_t i = 0; i < N_ARRS; i++) {
    arrays[i] = alloc_array(i * BASE_ARR_LEN);
  }

  // do some random accesses
  for (int pos = 1; pos < 100; pos++) {
    for (size_t i = 0; i < N_ARRS; i++) {
      arrays[i][i * BASE_ARR_LEN / pos] = 1;
    }
  }

  // leak memory
}

int main(int argc, char **argv) {
  run();
  malloc_stats_print(NULL, NULL, NULL);
  return 0;
}
