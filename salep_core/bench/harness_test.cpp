// bench/harness_test.cpp — kalıcı test (AŞAMA 1 collateral).
// CSV yükleyiciler + AUC + GA yardımcılarının birim doğrulaması.
// Kullanım: ./harness_test <demux_prefix>  (gen.py çıktısı).
#include <cmath>
#include <cstdio>
#include "harness.h"

static int fails = 0;
#define CHECK(c, msg)                                                   \
    do {                                                                \
        if (!(c)) {                                                     \
            std::printf("BATTI %s\n", msg);                             \
            fails++;                                                    \
        } else {                                                        \
            std::printf("OK %s\n", msg);                                \
        }                                                               \
    } while (0)

int main(int argc, char** argv) {
    if (argc < 2) {
        std::printf("kullanim: harness_test <demux_prefix>\n");
        return 2;
    }
    std::string pre = argv[1];

    // 1) AUC birim davranışları (sentetik, üreticiden bağımsız).
    {
        std::vector<int> y = {0, 0, 1, 1};
        std::vector<double> s1 = {0.1, 0.2, 0.8, 0.9};
        std::vector<double> s2 = {0.9, 0.8, 0.2, 0.1};
        std::vector<double> s3 = {0.5, 0.5, 0.5, 0.5};
        CHECK(std::fabs(bench::auc_mw(y, s1) - 1.0) < 1e-12, "auc-mukemmel=1");
        CHECK(std::fabs(bench::auc_mw(y, s2) - 0.0) < 1e-12, "auc-ters=0");
        CHECK(std::fabs(bench::auc_mw(y, s3) - 0.5) < 1e-12, "auc-bag=0.5");
        std::vector<int> y1 = {1, 1};
        CHECK(std::fabs(bench::auc_mw(y1, s1) - 0.5) < 1e-12, "auc-tek-sinif=0.5");
    }
    // 2) GA: bilinen örneklem.
    {
        std::vector<double> v = {2, 4, 4, 4, 5, 5, 7, 9};  // mean=5
        bench::Stats st = bench::stats_ci95(v);  // orneklem std=sqrt(32/7)
        CHECK(std::fabs(st.mean - 5.0) < 1e-9, "ga-ortalama=5");
        CHECK(std::fabs(st.std - std::sqrt(32.0 / 7.0)) < 1e-9, "ga-std");
        CHECK(st.lo95 < 5.0 && st.hi95 > 5.0, "ga-aralik");
    }
    // 3) Üretici CSV turu: tel + pencere tutarlılığı.
    {
        bench::WireTrace t;
        std::vector<bench::Window> w;
        CHECK(bench::load_wire_csv(pre + "_wire.csv", t), "tel-yukle");
        CHECK(bench::load_windows_csv(pre + "_windows.csv", w), "pencere-yukle");
        bool cover = true;
        for (auto& x : w) {
            if (x.t1 - x.t0 != 100) cover = false;
            if (x.t1 > (int)t.wire_q16.size()) cover = false;
        }
        CHECK(cover, "pencere-kapsama-100tick");
        // Etiket-bayrak tutarlılığı: has bayrakları label dizesiyle uyuşmalı.
        bool lbl = true;
        for (auto& x : w) {
            bool h4 = x.label.find("4") != std::string::npos;
            bool h12 = x.label.find("12") != std::string::npos;
            if ((int)h4 != x.has[0] || (int)h12 != x.has[1]) lbl = false;
        }
        CHECK(lbl, "etiket-bayrak-uyumu");
        std::printf("BILGI pencere=%d tick=%d\n", (int)w.size(),
                    (int)t.wire_q16.size());
    }
    std::printf(fails ? "HARNESS-TEST: BATTI\n" : "HARNESS-TEST: OK\n");
    return fails ? 1 : 0;
}
