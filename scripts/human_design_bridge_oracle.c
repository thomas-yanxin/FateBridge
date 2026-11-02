/* Independent exhaustive subset oracle. No production search or graph imports.
 * Input: 36 gate/center edges, then case identifier and active-gate bit mask.
 * Enumerate every absent-gate subset at each size through the first feasible
 * size. Union-find checks connectivity; all minimum subsets are retained.
 */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint64_t gates; int a, b; } Edge;
static Edge edges[36];
static int base[9], required[9], nrequired, candidates[64], ncandidates;
static uint64_t active, tested, *solutions;
static size_t nsolutions, capacity;

static int root(int *p, int x) {
    while (p[x] != x) x = p[x];
    return x;
}
static void unite(int *p, int a, int b) { p[root(p, a)] = root(p, b); }
static void evaluate(uint64_t added) {
    int p[9];
    memcpy(p, base, sizeof p);
    uint64_t gates = active | added;
    ++tested;
    for (int e = 0; e < 36; ++e)
        if ((gates & edges[e].gates) == edges[e].gates)
            unite(p, edges[e].a, edges[e].b);
    int representative = root(p, required[0]);
    for (int i = 1; i < nrequired; ++i)
        if (root(p, required[i]) != representative) return;
    if (nsolutions == capacity) {
        capacity = capacity ? capacity * 2 : 64;
        uint64_t *grown = realloc(solutions, capacity * sizeof *solutions);
        if (!grown) { fputs("oracle allocation failed\n", stderr); exit(3); }
        solutions = grown;
    }
    solutions[nsolutions++] = added;
}
static void enumerate(int index, int remaining, uint64_t chosen) {
    if (!remaining) { evaluate(chosen); return; }
    for (int i = index; i <= ncandidates - remaining; ++i)
        enumerate(i + 1, remaining - 1, chosen | (UINT64_C(1) << candidates[i]));
}
int main(void) {
    int nedges, ncases;
    if (scanf("%d", &nedges) != 1 || nedges != 36) return 2;
    for (int e = 0; e < 36; ++e) {
        int a, b, x, y;
        if (scanf("%d %d %d %d", &a, &b, &x, &y) != 4 ||
            a < 1 || a > 64 || b < 1 || b > 64 ||
            x < 0 || x > 8 || y < 0 || y > 8) return 2;
        edges[e] = (Edge){(UINT64_C(1) << (a - 1)) | (UINT64_C(1) << (b - 1)), x, y};
    }
    if (scanf("%d", &ncases) != 1 || ncases < 1) return 2;
    for (int c = 0; c < ncases; ++c) {
        char id[128];
        if (scanf("%127s %" SCNx64, id, &active) != 2) return 2;
        for (int i = 0; i < 9; ++i) base[i] = i;
        int defined[9] = {0};
        for (int e = 0; e < 36; ++e) if ((active & edges[e].gates) == edges[e].gates) {
            unite(base, edges[e].a, edges[e].b);
            defined[edges[e].a] = defined[edges[e].b] = 1;
        }
        nrequired = 0;
        for (int i = 0; i < 9; ++i) if (defined[i]) {
            int representative = root(base, i), found = 0;
            for (int j = 0; j < nrequired; ++j)
                if (root(base, required[j]) == representative) found = 1;
            if (!found) required[nrequired++] = i;
        }
        ncandidates = 0;
        for (int i = 0; i < 64; ++i)
            if (!(active & (UINT64_C(1) << i))) candidates[ncandidates++] = i;
        tested = 0; nsolutions = 0;
        int minimum = -1;
        if (nrequired > 1) for (int k = 0; k <= ncandidates; ++k) {
            enumerate(0, k, 0);
            if (nsolutions) { minimum = k; break; }
        }
        printf("{\"id\":\"%s\",\"original_component_count\":%d,"
               "\"minimum_added_gate_count\":%d,\"candidate_subsets_checked\":%" PRIu64
               ",\"minimum_sets\":[", id, nrequired, minimum, tested);
        for (size_t s = 0; s < nsolutions; ++s) {
            printf("%s[", s ? "," : "");
            int first = 1;
            for (int g = 0; g < 64; ++g) if (solutions[s] & (UINT64_C(1) << g)) {
                printf("%s%d", first ? "" : ",", g + 1); first = 0;
            }
            putchar(']');
        }
        puts("]}");
        fflush(stdout);
        fprintf(stderr, "%s: minimum=%d, solutions=%zu, subsets=%" PRIu64 "\n",
                id, minimum, nsolutions, tested);
    }
    free(solutions);
    return 0;
}
