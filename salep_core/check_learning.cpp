// REV-LEARN kontrolleri — iz + erisilebilirlik dinamigi.
// Repo convention (check_pattern_lobe.cpp): stdout raporlar, OZET + cikis.
// Kapsar: L0 (saf-yol eski formulle birebir), L1 (doyum: tavan + azalan
// marj), L2 (taban: kullanim-disinda iz-altina dusus YOK, iz sonmez),
// L3 (tasarruf: deneyimli, safa gore daha az maruziyette esige varir),
// L4 (eta=0 frozen: agirlik+iz bit-esit), L5 (determinizm),
// L6 (iz monoton + [0,1]).
#include <cstdio>
#include <cstring>
#include "synapse.h"

static const char* fx(fixed_t v) {
    static char b[8][32];
    static int i = 0;
    char* s = b[(i++) % 8];
    snprintf(s, 32, "%.6f", (double)fixed_to_float(v));
    return s;
}

static const fixed_t ETA = fixed_from_double(0.30);

int main() {
    int fails = 0;
    auto check = [&](const char* nm, bool ok, const char* extra = "") {
        printf("  %s %s %s\n", ok ? "OK" : "BATTI", nm, extra);
        if (!ok) fails++;
    };
    char buf[256];
    synapse_build_luts();

    // L0 saf-yol: T=0'da tek potansiyasyon == eski formul (compute_dw).
    {
        Synapse s;
        memset(&s, 0, sizeof(s));
        synapse_init(s, 0, 1, FIXED_ONE);
        fixed_t w0 = s.weight;
        fixed_t dw = synapse_apply_learning(s, 20, 20, ETA);
        fixed_t exp = synapse_compute_dw(20, 20, w0, ETA);
        bool ok = (dw == exp) && (s.weight == w0 + exp) && (s.trace > 0);
        snprintf(buf, 256, "dw=%s beklenen=%s iz=%s", fx(dw), fx(exp),
                 fx(s.trace));
        check("L0-saf-yol-birebir", ok, buf);
    }

    // L1 doyum: azami korelasyonda tavan + azalan marj.
    {
        Synapse s;
        memset(&s, 0, sizeof(s));
        synapse_init(s, 0, 1, FIXED_ONE);
        fixed_t w_first = 0, w_mid = 0;
        for (int t = 0; t < 2000; ++t) {
            synapse_apply_learning(s, RATE_WINDOW, RATE_WINDOW, ETA);
            if (t == 99) w_first = s.weight;
            if (t == 999) w_mid = s.weight;
        }
        fixed_t g1 = w_first - FIXED_ONE, g2 = s.weight - w_mid;
        bool ok = (s.weight <= W_MAX) && (s.weight > W_MAX - fixed_from_double(0.05)) &&
                  (g2 < g1) && (s.trace == FIXED_ONE || s.trace > FIXED_ONE - fixed_from_double(0.01));
        snprintf(buf, 256, "w=%s g100=%s gson900=%s iz=%s", fx(s.weight),
                 fx(g1), fx(g2), fx(s.trace));
        check("L1-doyum", ok, buf);
    }

    // L2a guclu-iz tabani: ogren + birak -> tepede kalir, iz sonmez.
    // (Not: tabana ~0.003 kala fixed-point LSB olu-bandi bozulmayi
    // dondurur — w taban USTUNDE durur, altina dusmez.)
    {
        Synapse s;
        memset(&s, 0, sizeof(s));
        synapse_init(s, 0, 1, FIXED_ONE);
        for (int t = 0; t < 200; ++t)
            synapse_apply_learning(s, RATE_WINDOW, RATE_WINDOW, ETA);
        fixed_t iz = s.trace;
        fixed_t taban = fixed_mul(iz, W_MAX);
        for (int t = 0; t < 3000; ++t)
            synapse_apply_learning(s, 0, 0, ETA);
        bool ok = (s.trace == iz) && (s.weight >= taban) && (s.weight > 0);
        snprintf(buf, 256, "iz=%s taban=%s w=%s", fx(iz), fx(taban),
                 fx(s.weight));
        check("L2a-taban-unutma-yok", ok, buf);
    }

    // L2b olculebilir gevse-me: hafif ogrenmede agirlik tabana dogru
    // ACILIR (dususu gozlenir) ama taban alti ve sifir YOK, iz sabit.
    {
        Synapse s;
        memset(&s, 0, sizeof(s));
        synapse_init(s, 0, 1, FIXED_ONE);
        for (int t = 0; t < 5; ++t)
            synapse_apply_learning(s, RATE_WINDOW, RATE_WINDOW, ETA);
        fixed_t wmid = s.weight, iz = s.trace;
        fixed_t taban = fixed_mul(iz, W_MAX);
        for (int t = 0; t < 2000; ++t)
            synapse_apply_learning(s, 0, 0, ETA);
        bool ok = (s.trace == iz) && (s.weight < wmid) &&
                  (s.weight >= taban) && (s.weight > 0);
        snprintf(buf, 256, "wmid=%s taban=%s wson=%s", fx(wmid), fx(taban),
                 fx(s.weight));
        check("L2b-gevseme-tabanli", ok, buf);
    }

    // L3 tasarruf: zayif ogrenme (10x8,8) + kullanim-disi sonrasi yaris:
    // deneyimli (iz-hizli) saf olandan az maruziyette 1.6'ya varir.
    // (Kalibrasyon: saf=28, deneyimli=8; deterministik, marjli esikler.)
    {
        Synapse a, b;
        memset(&a, 0, sizeof(a));
        memset(&b, 0, sizeof(b));
        synapse_init(a, 0, 1, FIXED_ONE);
        synapse_init(b, 0, 1, FIXED_ONE);
        for (int t = 0; t < 10; ++t)
            synapse_apply_learning(b, 8, 8, ETA);
        for (int t = 0; t < 1500; ++t)
            synapse_apply_learning(b, 0, 0, ETA);
        fixed_t hedef = fixed_from_double(1.6);
        int na = 0, nb = 0;
        while (a.weight < hedef && na < 5000) {
            synapse_apply_learning(a, 8, 8, ETA);
            na++;
        }
        while (b.weight < hedef && nb < 5000) {
            synapse_apply_learning(b, 8, 8, ETA);
            nb++;
        }
        bool ok = (na > 20) && (nb < 15) && (nb < na);
        snprintf(buf, 256, "saf=%d deneyimli=%d", na, nb);
        check("L3-tasarruf", ok, buf);
    }

    // L4 eta=0 frozen: agirlik + iz bit-esit.
    {
        Synapse s, ref;
        memset(&s, 0, sizeof(s));
        memset(&ref, 0, sizeof(ref));
        synapse_init(s, 0, 1, FIXED_ONE);
        synapse_init(ref, 0, 1, FIXED_ONE);
        fixed_t zero = fixed_from_double(0.0);
        for (int t = 0; t < 100; ++t)
            synapse_apply_learning(s, (t * 7) % 31, (t * 13) % 31, zero);
        bool ok = (memcmp(&s, &ref, sizeof(Synapse)) == 0);
        check("L4-eta0-frozen", ok, "");
    }

    // L5 determinizm: iki ayni kosu bit-esit.
    {
        Synapse s1, s2;
        memset(&s1, 0, sizeof(s1));
        memset(&s2, 0, sizeof(s2));
        synapse_init(s1, 0, 1, FIXED_ONE);
        synapse_init(s2, 0, 1, FIXED_ONE);
        for (int t = 0; t < 300; ++t) {
            int a = (t * 5 + 1) % 31, b = (t * 11 + 3) % 31;
            synapse_apply_learning(s1, a, b, ETA);
            synapse_apply_learning(s2, a, b, ETA);
        }
        bool ok = (memcmp(&s1, &s2, sizeof(Synapse)) == 0);
        check("L5-determinizm", ok, "");
    }

    // L6 iz monoton + [0,1].
    {
        Synapse s;
        memset(&s, 0, sizeof(s));
        synapse_init(s, 0, 1, FIXED_ONE);
        bool ok = true;
        fixed_t prev = 0;
        for (int t = 0; t < 500 && ok; ++t) {
            int a = (t % 3 == 0) ? 25 : 0;
            int b = (t % 3 == 0) ? 25 : 0;
            synapse_apply_learning(s, a, b, ETA);
            if (s.trace < prev || s.trace < 0 || s.trace > FIXED_ONE) ok = false;
            prev = s.trace;
        }
        snprintf(buf, 256, "iz=%s", fx(s.trace));
        check("L6-iz-monoton-sinirli", ok, buf);
    }

    printf("OZET-LEARN-CHECK: %s\n", fails ? "BATTI" : "OK");
    return fails ? 1 : 0;
}
