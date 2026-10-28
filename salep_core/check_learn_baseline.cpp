// REV-LEARN baseline kapilari (in-lobe, sentetik surus).
// LB1: eta0 cift-kosu bit-identical. LB2: eta03 cift-kosu bit-identical.
// LB3: ayni girdi eta0 vs eta03 -> W farkli, ON'da T>0, OFF'ta T==0.
// LB4: ogrenme K4 alanlarina sizmaz (V4cUnit, eta03 vs eta0 K4-esitligi).
// Cikti: OZET-LEARN-BASE + cikis kodu.
#include <cstdio>
#include <cstring>
#include "pattern_lobe.h"

int main() {
    int fails = 0;
    auto check = [&](const char* nm, bool ok, const char* extra = "") {
        printf("  %s %s %s\n", ok ? "OK" : "BATTI", nm, extra);
        if (!ok) fails++;
    };
    char buf[256];
    synapse_build_luts();

    auto run = [](P3x3Unit* u, fixed_t eta, int nt) {
        for (int t = 0; t < nt; ++t) {
            for (int i = 0; i < P3X3_N; ++i) {
                bool inj[P3X3_NSYN] = {};
                p3x3unit_drive(u[i], 1, t, inj);
                p3x3unit_drive(u[i], 4, t, inj);
                bool fr = p3x3_tick(u[i].n, t);
                p3x3unit_learn(u[i], inj, fr, eta);
            }
        }
    };
    const fixed_t ETA0 = fixed_from_double(0.0);
    const fixed_t ETA3 = fixed_from_double(0.30);

    // LB1: eta0 determinizm.
    {
        P3x3Unit a[P3X3_N], b[P3X3_N];
        memset(a, 0, sizeof(a));
        memset(b, 0, sizeof(b));
        for (int i = 0; i < P3X3_N; ++i) {
            p3x3unit_init_table(a[i], i);
            p3x3unit_init_table(b[i], i);
        }
        run(a, ETA0, 400);
        run(b, ETA0, 400);
        bool same = (memcmp(a, b, sizeof(a)) == 0);
        check("LB1-off-determinism", same, "");
    }
    // LB2: eta03 determinizm.
    {
        P3x3Unit a[P3X3_N], b[P3X3_N];
        memset(a, 0, sizeof(a));
        memset(b, 0, sizeof(b));
        for (int i = 0; i < P3X3_N; ++i) {
            p3x3unit_init_table(a[i], i);
            p3x3unit_init_table(b[i], i);
        }
        run(a, ETA3, 400);
        run(b, ETA3, 400);
        bool same = (memcmp(a, b, sizeof(a)) == 0);
        check("LB2-on-determinism", same, "");
    }
    // LB3: ogrenme devrede (W oynar, T>0) vs frozen (W==1, T==0).
    {
        P3x3Unit off[P3X3_N], on[P3X3_N];
        memset(off, 0, sizeof(off));
        memset(on, 0, sizeof(on));
        for (int i = 0; i < P3X3_N; ++i) {
            p3x3unit_init_table(off[i], i);
            p3x3unit_init_table(on[i], i);
        }
        run(off, ETA0, 400);
        run(on, ETA3, 400);
        int wmove = 0, tpos = 0, offclean = 1;
        for (int i = 0; i < P3X3_N; ++i)
            for (int k = 0; k < P3X3_NSYN; ++k) {
                const Synapse* so = p3x3_syn(off[i], k);
                const Synapse* sn = p3x3_syn(on[i], k);
                if (so->weight != fixed_from_double(1.0) || so->trace != 0)
                    offclean = 0;
                if (sn->weight != so->weight) wmove++;
                if (sn->trace > 0) tpos++;
            }
        snprintf(buf, 256, "wmove=%d tpos=%d offclean=%d", wmove, tpos,
                 offclean);
        check("LB3-on-ogrenir-off-donuk",
              offclean && wmove > 0 && tpos > 0, buf);
    }
    // LB4: ogrenme K4 durumuna dokunmaz.
    {
        V4cUnit a[P3X3_N], b[P3X3_N];
        memset(a, 0, sizeof(a));
        memset(b, 0, sizeof(b));
        for (int i = 0; i < P3X3_N; ++i) {
            v4c_init(a[i], i);
            v4c_init(b[i], i);
        }
        for (int t = 0; t < 400; ++t) {
            for (int i = 0; i < P3X3_N; ++i) {
                bool ia[P3X3_NSYN] = {}, ib[P3X3_NSYN] = {};
                p3x3unit_drive(a[i].base, 1, t, ia);
                p3x3unit_drive(a[i].base, 4, t, ia);
                p3x3unit_drive(b[i].base, 1, t, ib);
                p3x3unit_drive(b[i].base, 4, t, ib);
                bool fa = p3x3_tick(a[i].base.n, t);
                bool fb = p3x3_tick(b[i].base.n, t);
                p3x3unit_learn(a[i].base, ia, fa, ETA3);
                p3x3unit_learn(b[i].base, ib, fb, ETA0);
            }
        }
        bool same = true;
        for (int i = 0; i < P3X3_N && same; ++i)
            for (int d = 0; d < V4C_NDAL && same; ++d) {
                if (a[i].k4[d].local_voltage != b[i].k4[d].local_voltage)
                    same = false;
                if (a[i].k4_last_evt[d] != b[i].k4_last_evt[d]) same = false;
                if (a[i].k4_spike_tick[d] != b[i].k4_spike_tick[d])
                    same = false;
                if (a[i].k4_spiked[d] != b[i].k4_spiked[d]) same = false;
                if (a[i].k4_rel[d] != b[i].k4_rel[d]) same = false;
                if (a[i].k4_top[d] != b[i].k4_top[d]) same = false;
                if (a[i].k4_s4d[d] != b[i].k4_s4d[d]) same = false;
                if (a[i].k4_s4 != b[i].k4_s4) same = false;
            }
        check("LB4-k4-sizmasi-yok", same, "");
    }
    printf(fails ? "OZET-LEARN-BASE: BATTI (%d)\n" : "OZET-LEARN-BASE: OK\n",
           fails);
    return fails ? 1 : 0;
}
