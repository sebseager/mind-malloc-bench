#include <assert.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/random.h>
#include <time.h>
#include <unistd.h>

#define N_SLOTS (1 << 8)

typedef struct slot {
  unsigned long long n_allocs;
  unsigned long long n_frees;
  unsigned long long total_bytes;
  unsigned long long current_bytes;
  void *bytes;
} slot_t;

slot_t slots[N_SLOTS] = {0};

static unsigned long long lgc_next = 1;

// initialize seed for linear congruential generator (LCG)
void lcg_init(unsigned long long seed) { lgc_next = seed; }

// return a pseudorandom unsigned int in range [0, 2^64 - 1]
// uses MMIX LCG values from Knuth
// beware that this is likely NOT perfectly uniform due to modulo bias
// (front of the range may be more likely if max_len does not divide UINT_MAX)
unsigned long long lcg_rand() {
  lgc_next = lgc_next * 6364136223846793005ULL + 1442695040888963407ULL;
  return lgc_next;
}

// return a pseudorandom unsigned int in range [min, max]
unsigned int rand_between(unsigned int min, unsigned int max) {
  // use getrandom instead for actual randomness, doesn't add too much overhead
  // unsigned long long r;
  // getrandom(&r, sizeof(r), 0);
  // return min + (r % (max - min + 1));

  // as it turns out, rand() and getrandom() may both call malloc()
  // we want to avoid this, so make our own
  return min + (lcg_rand() % (max - min + 1));
}

void toggle_slot(int iter, int min_len, int max_len) {
  unsigned int i = iter % N_SLOTS; // use iter to choose slot
  if (slots[i].bytes == NULL) {
    unsigned int size = rand_between(min_len, max_len);
    slots[i].bytes = malloc(size);
    // update statistics
    slots[i].n_allocs += 1;
    slots[i].total_bytes += size;
    slots[i].current_bytes = size;
  } else {
    free(slots[i].bytes);
    slots[i].bytes = NULL;
    // update statistics
    slots[i].n_frees += 1;
    slots[i].current_bytes = 0;
  }
}

void run(int n_allocs, int min_len, int max_len) {
  // allocate a bunch of arrays
  for (size_t i = 0; i < n_allocs; i++) {
    toggle_slot(i, min_len, max_len);
  }
  // leak memory when done -- ok
}

void print_stats() {
  printf("%s %12s %12s %20s %18s\n", "slot_index", "allocs", "frees",
         "total_bytes", "current_bytes");
  for (size_t i = 0; i < N_SLOTS; i++) {
    printf("%10zu %12llu %12llu %20llu %18llu\n", i, slots[i].n_allocs,
           slots[i].n_frees, slots[i].total_bytes, slots[i].current_bytes);
  }
}

void print_time(struct timespec *start, struct timespec *end) {
  double elapsed = (end->tv_sec - start->tv_sec) +
                   (end->tv_nsec - start->tv_nsec) / 1000000000.0;
  printf("elapsed_secs %f\n", elapsed);
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
  assert(max_len < UINT_MAX); // in rand_between we may add 1 to max_len

  lcg_init(time(NULL)); // initialize rng with current time in seconds

  // time the run
  struct timespec start, end;
  clock_gettime(CLOCK_MONOTONIC, &start);
  run(n_allocs, min_len, max_len);
  clock_gettime(CLOCK_MONOTONIC, &end);

  // print statistics
  // warning: printf MAY call malloc, but this is a small constant cost
  //          as compared to the rest of the test
  print_time(&start, &end);
  print_stats();

  return 0;
}



// TODO
// measure mmap time per malloc call
//   sum elapsed mmap time / number of malloc calls = average mmap time
//   as low as possible
// don't mess with munmap as much -- don't care about freeing
//    also don't care about munmap_recl
// pthread for multiple threads
// https://www.tutorialspoint.com/multithreading-in-c
