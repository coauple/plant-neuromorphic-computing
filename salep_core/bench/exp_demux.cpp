// bench/exp_demux.cpp — demux deneyi S-kolu (AŞAMA 2/3/4/5 ortak binası).
// Çekirdeği include eder, DEĞİŞTİRMEZ. Girdi: gen.py tel CSV'si (Q16.16 tamsayı).
// Kullanım:
//   exp_demux --wire F --taus 4,12 --pops 8,8 --plir 1 --seed 7001 --win 100 --out P
// Çıktı: P_tick.csv (tick,b0,b1: bant-başına ateş/ tick),
//        P_win.csv (wid,t0,t1,b0sum,b1sum: pencere toplamları).
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "../src/fdm.h"

namespace {
std::vector<int> parse_ints(const char* s) {
    std::vector<int> out;
    const char* p = s;
    while (*p) {
        out.push_back(atoi(p));
        while (*p && *p != ',') ++p;
        if (*p == ',') ++p;
    }
    return out;
}
}  // namespace

int main(int argc, char** argv) {
    const char* wire_path = nullptr;
    const char* out_pre = nullptr;
    std::vector<int> taus, pops;
    int plir = 1, win = 100;
    uint32_t seed = 7001;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--wire") == 0 && i + 1 < argc) wire_path = argv[++i];
        else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) out_pre = argv[++i];
        else if (strcmp(argv[i], "--taus") == 0 && i + 1 < argc) taus = parse_ints(argv[++i]);
        else if (strcmp(argv[i], "--pops") == 0 && i + 1 < argc) pops = parse_ints(argv[++i]);
        else if (strcmp(argv[i], "--plir") == 0 && i + 1 < argc) plir = atoi(argv[++i]);
        else if (strcmp(argv[i], "--seed") == 0 && i + 1 < argc) seed = (uint32_t)atoi(argv[++i]);
        else if (strcmp(argv[i], "--win") == 0 && i + 1 < argc) win = atoi(argv[++i]);
        else { std::fprintf(stderr, "bilinmeyen arguman %s\n", argv[i]); return 2; }
    }
    if (!wire_path || !out_pre || taus.empty() || taus.size() > 2) {
        std::fprintf(stderr, "kullanim: exp_demux --wire F --taus a[,b] "
                             "[--pops ..] [--plir 0|1] [--seed N] [--win W] --out P\n");
        return 2;
    }
    while (pops.size() < taus.size()) pops.push_back(FDM_N_POP);
    for (size_t b = 0; b < taus.size(); ++b) {
        if (taus[b] < 1 || taus[b] > FDM_TAU_MAX || pops[b] < 1 || pops[b] > FDM_MAX_POP) {
            std::fprintf(stderr, "HATA: tau/pop araligi (tau<=16, pop<=14)\n");
            return 2;
        }
    }
    FILE* f = fopen(wire_path, "r");
    if (!f) { std::fprintf(stderr, "HATA: tel acilmadi\n"); return 1; }
    std::vector<int32_t> wire;
    char line[256];
    if (!fgets(line, sizeof(line), f)) return 1;  // başlık
    while (fgets(line, sizeof(line), f)) {
        char* c = strchr(line, ',');
        if (!c) continue;
        wire.push_back((int32_t)strtol(c + 1, nullptr, 10));
    }
    fclose(f);

    FdmNetwork net;
    int32_t ta[3] = {0, 0, 0};
    int po[3] = {0, 0, 0};
    for (size_t b = 0; b < taus.size(); ++b) { ta[b] = taus[b]; po[b] = pops[b]; }
    fdm_init(net, ta, po, (int)taus.size(), plir, seed);

    std::string tp = std::string(out_pre) + "_tick.csv";
    std::string wp = std::string(out_pre) + "_win.csv";
    FILE* tf = fopen(tp.c_str(), "w");
    FILE* wf = fopen(wp.c_str(), "w");
    if (!tf || !wf) { std::fprintf(stderr, "HATA: cikti acilmadi\n"); return 1; }
    fprintf(tf, "tick,b0,b1\n");
    fprintf(wf, "wid,t0,t1,b0sum,b1sum\n");
    long acc[2] = {0, 0};
    int wid = 0;
    for (size_t t = 0; t < wire.size(); ++t) {
        FdmTickFires fr = fdm_tick(net, (int32_t)t, wire[t]);
        int per[2] = {0, 0};
        for (size_t b = 0; b < taus.size(); ++b) {
            for (int m = 0; m < po[b]; ++m)
                if (fr.fired[b][m]) per[b]++;
            acc[b] += per[b];
        }
        fprintf(tf, "%d,%d,%d\n", (int)t, per[0], taus.size() > 1 ? per[1] : 0);
        if ((int)t % win == win - 1) {
            int t0 = (int)t - win + 1;
            fprintf(wf, "%d,%d,%d,%ld,%ld\n", wid++, t0, (int)t + 1, acc[0],
                    taus.size() > 1 ? acc[1] : 0);
            acc[0] = acc[1] = 0;
        }
    }
    // Kuyruk (tam-pencere değilse yine yaz, etiketleyici karar verir).
    if (!wire.empty() && (int)wire.size() % win != 0) {
        int t0 = (int)(wire.size() / win * win);
        fprintf(wf, "%d,%d,%d,%ld,%ld\n", wid, t0, (int)wire.size(), acc[0],
                taus.size() > 1 ? acc[1] : 0);
    }
    fclose(tf);
    fclose(wf);
    std::printf("OK demux: %d tick, %d pencere\n", (int)wire.size(), wid);
    return 0;
}
