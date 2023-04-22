#include <assert.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/random.h>
#include <time.h>
#include <unistd.h>

#define BYTE_SIZE 8
#define ALLOCS_PER_ROUND (1 << 10)

// === RANDOM NUMBER GENERATOR ===

// global generator state
static unsigned long long lgc_next = 1;

// initialize seed for linear congruential generator (LCG)
void lcg_init(unsigned long long seed) { lgc_next = seed; }

// return a pseudorandom unsigned int in range [0, 2^64 - 1]
// uses MMIX LCG values from Knuth
// beware that this is likely NOT uniform due to modulo bias
// (front of the range may be more likely if max_len does not divide UINT_MAX)
unsigned long long lcg_rand() {
  lgc_next = lgc_next * 6364136223846793005ULL + 1442695040888963407ULL;
  return lgc_next;
}

// return a pseudorandom unsigned int in range [min, max]
unsigned int rand_between(unsigned int min, unsigned int max) {
  // as it turns out, rand() and getrandom() may both call malloc()
  // we want to avoid this, so make our own
  return min + (lcg_rand() % (max - min + 1));
}

// === TIMING ===

void set_time(struct timespec *ts) { clock_gettime(CLOCK_REALTIME, ts); }

// === ALLOCATION ===

typedef struct round {
  unsigned int round_num;
  unsigned long long n_allocs;
  unsigned long long n_bytes;
  struct timespec start_alloc;
  struct timespec end_alloc;
  void *slots[ALLOCS_PER_ROUND];
} round_t;

void run_round(round_t *r, int min_alloc, int max_alloc) {
  // record start time
  set_time(&r->start_alloc);

  // allocate a bunch of random sizes
  for (int i = 0; i < ALLOCS_PER_ROUND; i++) {
    unsigned int len = rand_between(min_alloc, max_alloc) * BYTE_SIZE;
    r->slots[i] = malloc(len);
    r->n_allocs++;
    r->n_bytes += len;
  }

  // record end time
  set_time(&r->end_alloc);

  // free everything
  for (int i = 0; i < ALLOCS_PER_ROUND; i++) {
    free(r->slots[i]);
  }
}

// === STATISTICS ===

void print_stats_header() {
  printf("round\tallocs\ttotal_bytes\talloc_start_time\talloc_end_time\n");
}

void print_round_stats(round_t *r) {
  printf("%d\t", r->round_num);
  printf("%llu\t", r->n_allocs);
  printf("%llu\t", r->n_bytes);

  // limit nanosecond portion to 6 digits to match strace
  printf("%ld.%09ld\t", r->start_alloc.tv_sec, r->start_alloc.tv_nsec);
  printf("%ld.%09ld\n", r->end_alloc.tv_sec, r->end_alloc.tv_nsec);
}

// === MAIN ===

void run(int n_rounds, int min_alloc, int max_alloc) {
  round_t rounds[n_rounds];
  print_stats_header();
  for (int i = 0; i < n_rounds; i++) {
    rounds[i].round_num = i;
    run_round(&rounds[i], min_alloc, max_alloc);
    print_round_stats(&rounds[i]);
  }
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

  // initialization
  lcg_init(time(NULL));

  // run the test
  run(n_allocs, min_len, max_len);

  return 0;
}

// pthread for multiple threads
// https://www.tutorialspoint.com/multithreading-in-c
