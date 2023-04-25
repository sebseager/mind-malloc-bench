#include <assert.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define BYTE_SIZE 8
#define NS_PER_SEC 1000000000ULL
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
  int thread_id;
  void *slots[ALLOCS_PER_ROUND];

  // statistics
  unsigned long long n_allocs;
  unsigned long long n_bytes;
  struct timespec start_alloc;
  struct timespec end_alloc;
} round_t;

void run_round(round_t *r, unsigned int min_bytes, unsigned int max_bytes) {
  // record start time
  set_time(&r->start_alloc);

  // allocate a bunch of random sizes
  r->n_allocs = 0;
  r->n_bytes = 0;
  for (int i = 0; i < ALLOCS_PER_ROUND; i++) {
    unsigned int len = rand_between(min_bytes, max_bytes) * BYTE_SIZE;
    r->slots[i] = malloc(len);
    r->n_allocs++;
    r->n_bytes += len;
  }

  // // random access
  // for (int i = 0; i < ALLOCS_PER_ROUND; i++) {
  //   memset(r->slots[i], 0, min_bytes * BYTE_SIZE);
  // }

  // record end time
  set_time(&r->end_alloc);

  // free everything
  for (int i = 0; i < ALLOCS_PER_ROUND; i++) {
    free(r->slots[i]);
  }
}

// === STATISTICS ===

void print_stats_header() {
  printf("round\t");
  printf("thread\t");
  printf("allocs\t");
  printf("total_bytes\t");
  printf("alloc_start_ns\t");
  printf("alloc_end_ns\n");
}

void print_round_stats(round_t *r) {
  printf("%d\t", r->round_num);
  printf("%d\t", r->thread_id);
  printf("%llu\t", r->n_allocs);
  printf("%llu\t", r->n_bytes);

  // convert timespec to nanoseconds
  unsigned long long start_ns =
      r->start_alloc.tv_sec * NS_PER_SEC + r->start_alloc.tv_nsec;
  unsigned long long end_ns =
      r->end_alloc.tv_sec * NS_PER_SEC + r->end_alloc.tv_nsec;
  printf("%llu\t", start_ns);
  printf("%llu\n", end_ns);
}

// === MAIN ===

typedef struct thread {
  pthread_t pthread;
  round_t *rounds;
  int n_rounds;
  int n_threads;
  int thread_id;
  int min_bytes;
  int max_bytes;
} thread_t;

void *run_thread(void *thread) {
  thread_t *t = (thread_t *)thread;
  int rounds_per_thread = t->n_rounds / t->n_threads;
  int extra_rounds = t->n_rounds % t->n_threads;
  if (t->thread_id < extra_rounds) {
    rounds_per_thread++;
  }

  // perform work on rounds assigned to this thread
  // assigns rounds to threads in a round-robin fashion
  for (int i = 0; i < rounds_per_thread; i++) {
    int num = t->thread_id + i * t->n_threads;
    t->rounds[num].thread_id = t->thread_id;
    run_round(&t->rounds[num], t->min_bytes, t->max_bytes);
  }

  return NULL;
}

void start(int n_rounds, int min_bytes, int max_bytes, int n_threads) {
  round_t rounds[n_rounds];
  for (int i = 0; i < n_rounds; i++) {
    rounds[i].round_num = i;
  }

  thread_t threads[n_threads];
  for (int i = 0; i < n_threads; i++) {
    threads[i].rounds = rounds;
    threads[i].n_rounds = n_rounds;
    threads[i].n_threads = n_threads;
    threads[i].thread_id = i;
    threads[i].min_bytes = min_bytes;
    threads[i].max_bytes = max_bytes;
  }

  // start all threads
  for (int i = 0; i < n_threads; i++) {
    pthread_create(&threads[i].pthread, NULL, run_thread, &threads[i]);
  }

  // wait for all threads to finish up
  for (int i = 0; i < n_threads; i++) {
    pthread_join(threads[i].pthread, NULL);
  }

  // print stats
  print_stats_header();
  for (int i = 0; i < n_rounds; i++) {
    print_round_stats(&rounds[i]);
  }
}

int main(int argc, char **argv) {
  // check that two parameters are passed
  if (argc < 5) {
    printf("Usage: %s n_rounds min_bytes max_bytes n_threads\n", argv[0]);
    return 1;
  }

  // parse parameters
  unsigned int n_rounds = atoi(argv[1]);
  unsigned int min_bytes = atoi(argv[2]);
  unsigned int max_bytes = atoi(argv[3]);
  unsigned int n_threads = atoi(argv[4]);

  // validate parameters
  assert(n_rounds > 0);
  assert(min_bytes > 0);
  assert(max_bytes >= min_bytes);
  assert(max_bytes < UINT_MAX); // in rand_between we may add 1 to max_len
  assert(n_threads > 0);
  assert(n_threads <= n_rounds);
  assert(n_rounds % n_threads == 0); // for simplicity

  // initialization
  lcg_init(time(NULL));

  // run the test
  start(n_rounds, min_bytes, max_bytes, n_threads);

  return 0;
}

// pthread for multiple threads
// https://www.tutorialspoint.com/multithreading-in-c
