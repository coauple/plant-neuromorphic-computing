#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "src/fdm.h"
int main(int argc, char** argv) {
    FILE* f = fopen(argv[1], "r");
    std::vector<int32_t> wire;
    char line[256];
    if (!fgets(line, sizeof(line), f)) return 1;
    while (fgets(line, sizeof(line), f)) {
        char* c = strchr(line, ',');
        if (c) wire.push_back((int32_t)strtol(c + 1, nullptr, 10));
    }
    fclose(f);
    FdmNetwork net;
    int32_t ta[3] = {4, 12, 0};
    int po[3] = {8, 8, 0};
    bench_cnt_mul = 0;
    bench_cnt_div = 0;
    fdm_init(net, ta, po, 2, 1, 7001);
    long init_mul = bench_cnt_mul, init_div = bench_cnt_div;
    for (size_t t = 0; t < wire.size(); ++t) fdm_tick(net, (int32_t)t, wire[t]);
    long n = (long)wire.size();
    printf("tick=%ld toplam_mul=%ld toplam_div=%ld mul_per_tick=%.2f div_per_tick=%.4f (init haric: mul=%ld div=%ld)\n",
           n, bench_cnt_mul, bench_cnt_div,
           (double)(bench_cnt_mul - init_mul) / n,
           (double)(bench_cnt_div - init_div) / n,
           bench_cnt_mul - init_mul, bench_cnt_div - init_div);
    return 0;
}
