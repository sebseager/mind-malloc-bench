#include <assert.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define N_ARRAYS (1 << 10)
#define ERROR(...)                                                             \
  {                                                                            \
    printf(__VA_ARGS__);                                                       \
    return 1;                                                                  \
  }

int *arrays[N_ARRAYS] = {0};

// get random unsigned int from /dev/urandom
unsigned int rand_uint() {
  int fd = open("/dev/urandom", O_RDONLY);
  if (fd < 0)
    ERROR("failed to open /dev/urandom");
  unsigned int r;
  if (read(fd, &r, sizeof(r)) != sizeof(r))
    ERROR("failed to read from /dev/urandom");
  close(fd);
  return r;
}

// generate random unsigned int in [min_len, max_len]
// beware that this is likely not perfectly uniform due to modulo bias
// (front of the range may be more likely if max_len does not divide UINT_MAX)
unsigned int rand_between(unsigned int min, unsigned int max) {
  assert(min <= max);
  assert(max < UINT_MAX); // avoid overflow since we add 1 to max_len
  return min + (rand_uint() % (max - min + 1));
}

int *rand_alloc(unsigned int min_len, unsigned int max_len) {
  unsigned int len = rand_between(min_len, max_len);
  return malloc(len * sizeof(int));
}

void run(int n_allocs, int min_len, int max_len) {
  // allocate a bunch of arrays
  for (size_t i = 0; i < n_allocs; i++) {
    unsigned int j = rand_between(0, N_ARRAYS - 1);
    if (arrays[j] == NULL) {
      arrays[j] = rand_alloc(min_len, max_len);
    } else {
      free(arrays[j]);
      arrays[j] = NULL;
    }
  }
  // leak memory -- ok
}

int main(int argc, char **argv) {
  // check that two parameters are passed
  if (argc != 4) {
    printf("Usage: %s n_allocs min_len max_len\n", argv[0]);
    return 1;
  }

  // parse parameters
  unsigned int n_allocs = atoi(argv[1]);
  unsigned int min_len = atoi(argv[2]);
  unsigned int max_len = atoi(argv[3]);

  // validate parameters
  assert(n_allocs > 0);
  assert(min_len > 0);
  assert(max_len >= min_len);

  run(n_allocs, min_len, max_len);
  return 0;
}
