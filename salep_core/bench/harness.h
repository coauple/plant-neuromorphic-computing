// bench/harness.h — bağımsız değerlendirme ortak altyapısı (AŞAMA 1).
// YALNIZ harness: CSV okuma + metrikler (double serbest). Çekirdek .h
// dosyalarına dokunmaz, onları include etmez (Aşama 2'de deney .cpp'leri eder).
#ifndef BENCH_HARNESS_H
#define BENCH_HARNESS_H

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <numeric>
#include <sstream>
#include <string>
#include <vector>

namespace bench {

struct WireTrace {
    std::vector<int32_t> wire_q16;  // tick indeksli, Q16.16 tamsayı
};

struct Window {
    int id, t0, t1;
    std::string label;
    std::vector<int> has;  // hedef ritim sırasına göre 0/1
};

struct Event {
    int32_t tick;
    char kind;  // 'X' | 'Y'
    int link;   // X: öz-id; Y-bağlı: X-id; Y-sahte: -1
};

inline std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> out;
    std::string cur;
    std::istringstream ss(line);
    while (std::getline(ss, cur, ',')) out.push_back(cur);
    return out;
}

inline bool load_wire_csv(const std::string& path, WireTrace& t) {
    std::ifstream f(path);
    if (!f) return false;
    std::string line;
    std::getline(f, line);  // başlık
    t.wire_q16.clear();
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        auto c = split_csv(line);
        if (c.size() < 2) return false;
        t.wire_q16.push_back((int32_t)std::stol(c[1]));
    }
    return !t.wire_q16.empty();
}

inline bool load_windows_csv(const std::string& path, std::vector<Window>& w) {
    std::ifstream f(path);
    if (!f) return false;
    std::string line;
    std::getline(f, line);
    w.clear();
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        auto c = split_csv(line);
        if (c.size() < 5) return false;
        Window x;
        x.id = std::stoi(c[0]);
        x.t0 = std::stoi(c[1]);
        x.t1 = std::stoi(c[2]);
        x.label = c[3];
        for (size_t i = 4; i < c.size(); ++i) x.has.push_back(std::stoi(c[i]));
        w.push_back(x);
    }
    return !w.empty();
}

inline bool load_events_csv(const std::string& path, std::vector<Event>& e) {
    std::ifstream f(path);
    if (!f) return false;
    std::string line;
    std::getline(f, line);
    e.clear();
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        auto c = split_csv(line);
        if (c.size() < 3) return false;
        Event x;
        x.tick = (int32_t)std::stol(c[0]);
        x.kind = c[1].empty() ? '?' : c[1][0];
        x.link = std::stoi(c[2]);
        e.push_back(x);
    }
    return !e.empty();
}

// Eşiksiz AUC (Mann-Whitney U / (n0*n1)); bağlar 0.5 sayılır.
inline double auc_mw(const std::vector<int>& y,
                     const std::vector<double>& s) {
    std::vector<double> p, n;
    for (size_t i = 0; i < y.size(); ++i) {
        if (y[i])
            p.push_back(s[i]);
        else
            n.push_back(s[i]);
    }
    if (p.empty() || n.empty()) return 0.5;
    double u = 0.0;
    for (double a : p)
        for (double b : n) {
            if (a > b)
                u += 1.0;
            else if (a == b)
                u += 0.5;
        }
    return u / ((double)p.size() * (double)n.size());
}

struct Stats {
    double mean, std, lo95, hi95;
    int n;
};

// Örneklem std (n-1) + normal-yaklaşım %95 GA.
inline Stats stats_ci95(const std::vector<double>& v) {
    Stats r{0, 0, 0, 0, (int)v.size()};
    if (v.empty()) return r;
    r.mean = std::accumulate(v.begin(), v.end(), 0.0) / v.size();
    if (v.size() > 1) {
        double s2 = 0.0;
        for (double x : v) s2 += (x - r.mean) * (x - r.mean);
        r.std = std::sqrt(s2 / (v.size() - 1));
        double e = 1.96 * r.std / std::sqrt((double)v.size());
        r.lo95 = r.mean - e;
        r.hi95 = r.mean + e;
    } else {
        r.lo95 = r.hi95 = r.mean;
    }
    return r;
}

}  // namespace bench

#endif  // BENCH_HARNESS_H
