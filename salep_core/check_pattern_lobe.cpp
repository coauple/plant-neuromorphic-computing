// REV4 kontrolleri — gercek K4 + frozen v3e korunumu.
// Repo convention (check_pattern_unit_v3e.cpp): stdout raporlar, OZET + cikis kodu.
// Kapsar: J0 (k4-kapali memcmp bit-identical), C1 (coin yok -> r=0),
// C2 (pairwise-lokalite: yalniz eslesen dal cifti dolar), C3 (farkli pencere
// soner), C4 (farkli kimlik soner), M (bounded: r<=1, rel<=1, V4<=15,
// S4<=cap), N (yerel surussuz + K4-tonik birim ateslemez; K4 spike'i sart),
// E (determinizm), P (matris nonuniform), S1 (max-not-sum + argmax),
// S2 (ayni gucte partner degisimi -> argmax flip), S3 (K4 salimi somayi
// nedensel belirler: ayni S123, salimli ates / salimsiz sessiz).
#include <cstdio>
#include <cstring>
#include "pattern_lobe.h"

static const char* fx(fixed_t v) {
    static char b[8][32];
    static int i = 0;
    char* s = b[(i++) % 8];
    snprintf(s, 32, "%.6f", (double)fixed_to_float(v));
    return s;
}

// Sentetik ham dal kimligi: aktif-kompartman kumesiyle kurulur.
static void mkid(V4cIdentity& id, bool k1, bool k2, bool k3) {
    fixed_t hi = GATING_ACTIVATE_THRESH + fixed_from_double(0.5);
    id.v[0] = k1 ? hi : V_REST;
    id.v[1] = k2 ? hi : V_REST;
    id.v[2] = k3 ? hi : V_REST;
}

// Sentetik imza: ham kimlikten nicemlenir (uretim yoluyla ayni).
static void mksig(V4cSig& s, bool k1, bool k2, bool k3) {
    V4cIdentity id;
    mkid(id, k1, k2, k3);
    v4c_quantize(id, s);
}

int main() {
    int fails = 0;
    auto check = [&](const char* nm, bool ok, const char* extra = "") {
        printf("  %s %s %s\n", ok ? "OK" : "BATTI", nm, extra);
        if (!ok) fails++;
    };
    char buf[256];

    synapse_build_luts();

    // J0 k4-kapali bit-identical (K4 alanlari init degerinde + ates esitligi
    // + memcmp).
    {
        V4cUnit a[P3X3_N];
        P3x3Unit b[P3X3_N];
        memset(a, 0, sizeof(a));
        memset(b, 0, sizeof(b));
        for (int i = 0; i < P3X3_N; ++i) {
            v4c_init(a[i], i);
            p3x3unit_init_table(b[i], i);
        }
        fixed_t eta0 = fixed_from_double(0.0);
        int fa = 0, fb = 0;
        for (int t = 0; t < 120; ++t) {
            int s = (t * 5 + 1) % 12;
            for (int i = 0; i < P3X3_N; ++i) {
                bool ia[P3X3_NSYN] = {}, ib[P3X3_NSYN] = {};
                p3x3unit_drive(a[i].base, s, t, ia);
                p3x3unit_drive(b[i], s, t, ib);
                // k4 kapali: snapshot/net/tick/soma YOK (main'deki if(k4_on)).
                bool fra = p3x3_tick(a[i].base.n, t);
                bool frb = p3x3_tick(b[i].n, t);
                p3x3unit_learn(a[i].base, ia, fra, eta0);
                p3x3unit_learn(b[i], ib, frb, eta0);
                fa += fra ? 1 : 0;
                fb += frb ? 1 : 0;
            }
        }
        bool same = (fa == fb);
        for (int i = 0; i < P3X3_N && same; ++i)
            if (memcmp(&a[i].base, &b[i], sizeof(P3x3Unit)) != 0) same = false;
        for (int i = 0; i < P3X3_N && same; ++i)
            for (int d = 0; d < V4C_NDAL && same; ++d) {
                if (a[i].k4[d].local_voltage != V_REST) same = false;
                if (a[i].k4_last_evt[d] != -1) same = false;
                if (a[i].k4_spike_tick[d] != -1) same = false;
                if (a[i].k4_spiked[d]) same = false;
                if (a[i].k4_rel[d] != 0) same = false;
                if (a[i].k4_top[d] != -1) same = false;
                if (a[i].k4_s4d[d] != 0) same = false;
                if (a[i].k4_s4 != 0) same = false;
            }
        snprintf(buf, 256, "ates=%d/%d memcmp=%d", fa, fb, (int)!same);
        check("J0-kapali-bit-identical", same, buf);
    }

    // C1 coincidence yok -> tum r=0 (imzalar eslesse bile).
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], true, false, true);  // hepsi ayni imza
            evts[b] = -1;                        // hic olay yok
        }
        for (int t = 0; t < 30; ++t) v4c_net_update(net, sigs, evts, t);
        bool allzero = true;
        for (int a = 0; a < V4C_NB && allzero; ++a)
            for (int b = 0; b < V4C_NB && allzero; ++b)
                if (net.r[a][b] != 0) allzero = false;
        check("C1-coinsiz-sifir", allzero, "");
    }

    // C2 pairwise-lokalite: yalniz eslesen dal cifti dolar, komsular 0.
    // (cift (1,1,0) vs zemin (0,0,0): pay 12 < 13 -> kapali.)
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], false, false, false);
            evts[b] = -1;
        }
        mksig(sigs[0], true, true, false);
        mksig(sigs[1], true, true, false);  // 0-1 cifti eslesir (pay 18)
        for (int t = 0; t < 20; ++t) {
            evts[0] = t;
            evts[1] = t;  // ayni pencere
            v4c_net_update(net, sigs, evts, t);
        }
        bool pair_grew = (net.r[0][1] > fixed_from_double(0.8));
        bool others_zero = true;
        for (int b = 2; b < V4C_NB && others_zero; ++b)
            if (net.r[0][b] != 0 || net.r[1][b] != 0) others_zero = false;
        snprintf(buf, 256, "r01=%s", fx(net.r[0][1]));
        check("C2-pairwise-lokalite", pair_grew && others_zero, buf);
    }

    // C3 farkli pencere -> soner: once doldur, sonra ayir.
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], true, false, true);
            evts[b] = -1;
        }
        for (int t = 0; t < 20; ++t) {  // doldur (r~0.93)
            evts[0] = t;
            evts[1] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        // NOT: pencere hafizasi 10 tick oldugundan ayrilik sonrasi ilk
        // 10 tick coin=true kalir (1'in son olayi 19). Gercek sonum
        // 10 tick pencere-eskimesi + 25 tick bozunumla olculur.
        for (int t = 20; t < 55; ++t) {  // ayir: 0 tikler, 1 susar
            evts[0] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        bool decayed = (net.r[0][1] <= fixed_from_double(0.1));
        snprintf(buf, 256, "r01=%s", fx(net.r[0][1]));
        check("C3-farkli-pencere-soner", decayed, buf);
    }

    // C4 farkli kimlik + ayni pencere -> dolar degil (sifir kalir).
    // ((1,1,1) vs (0,0,0): pay 9 < 13.)
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], false, false, false);
            evts[b] = -1;
        }
        mksig(sigs[2], true, true, true);
        mksig(sigs[3], false, false, false);
        for (int t = 0; t < 20; ++t) {
            evts[2] = t;
            evts[3] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        bool still = (net.r[2][3] == 0);
        snprintf(buf, 256, "r23=%s", fx(net.r[2][3]));
        check("C4-farkli-kimlik-dolmaz", still, buf);
    }

    // M bounded: asiri-ciftlesmede r<=REL_MAX, rel<=1, V4<=15, S4<=cap.
    // (V4* <= (LOC+1)/0.08 = 14.0625 yapisal; 15 marjli.)
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], true, true, true);  // hepsi ayni
            evts[b] = 0;
        }
        for (int t = 0; t < 200; ++t) {
            for (int b = 0; b < V4C_NB; ++b) evts[b] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        bool ok = true;
        for (int a = 0; a < V4C_NB && ok; ++a)
            for (int b = 0; b < V4C_NB && ok; ++b)
                if (net.r[a][b] < 0 || net.r[a][b] > V4C_REL_MAX) ok = false;
        bool pspk[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) pspk[b] = true;  // tonik spike
        Compartment k;
        compartment_init(k);
        k.leak_rate = fixed_from_double(0.08);
        k.gating_decay_rate = fixed_from_double(0.005);
        int32_t spt = -1;
        fixed_t vmax = 0, s4max = 0;
        for (int t = 0; t < 200 && ok; ++t) {
            int top = -1;
            fixed_t rel = v4c_branch_rel(net, sigs, pspk, 0, top);
            if (rel < 0 || rel > FIXED_ONE) ok = false;
            v4c_k4_tick(k, V4C_K4_LOC, rel, t, spt);
            if (k.local_voltage > vmax) vmax = k.local_voltage;
            fixed_t s4 = v4c_soma_s4(v4c_k4_release(k), v4c_k4_release(k));
            if (s4 > s4max) s4max = s4;
        }
        if (vmax > fixed_from_double(15.0)) ok = false;
        if (s4max > V4C_S4_CAP) ok = false;
        snprintf(buf, 256, "r01=%s vmax=%s s4max=%s", fx(net.r[0][1]),
                 fx(vmax), fx(s4max));
        check("M-bounded", ok, buf);
    }

    // N: yerel-surussuz birim, K4 tonik-max surulse bile ateslemez — ve K4
    // gercekten spike'lar (bos test degil). S4<=cap yapisal (min).
    {
        V4cUnit u;
        memset(&u, 0, sizeof(u));
        v4c_init(u, 6);
        int fires = 0, ksp = 0;
        fixed_t s4max = 0;
        bool injected[P3X3_NSYN] = {};
        for (int t = 0; t < 200; ++t) {
            p3x3_tick(u.base.n, t);  // yerel surus YOK
            for (int d = 0; d < V4C_NDAL; ++d) {
                // tonik-max iliskisel surus, lokal sarj yok
                if (v4c_k4_tick(u.k4[d], 0, FIXED_ONE, t,
                                u.k4_spike_tick[d]))
                    ksp++;
            }
            fixed_t s4 = v4c_soma_s4(v4c_k4_release(u.k4[0]),
                                     v4c_k4_release(u.k4[1]));
            if (s4 > s4max) s4max = s4;
            if (v4c_soma_fire(u.base, u.k4, u.base.n.soma_voltage, s4, t))
                fires++;
            (void)injected;
        }
        snprintf(buf, 256, "ates=%d kspike=%d s4max=%s", fires, ksp,
                 fx(s4max));
        check("N-surussuz-aktive-olmaz",
              fires == 0 && ksp > 0 && s4max <= V4C_S4_CAP, buf);
    }

    // E determinizm: iki ag ayni girdi -> matris bit-esit.
    {
        V4cK4Net n1, n2;
        v4c_net_init(n1);
        v4c_net_init(n2);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], (b % 3) == 0, (b % 3) == 1, (b % 2) == 0);
            evts[b] = -1;
        }
        for (int t = 0; t < 40; ++t) {
            for (int b = 0; b < V4C_NB; ++b)
                if (((t + b) % 4) == 0) evts[b] = t;
            v4c_net_update(n1, sigs, evts, t);
            v4c_net_update(n2, sigs, evts, t);
        }
        bool det = (memcmp(&n1, &n2, sizeof(n1)) == 0);
        check("E-determinizm", det, "");
    }

    // P matris nonuniform: karisik dunyada sifir + dolu hucre bir arada.
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], (b % 2) == 0, false, (b % 3) == 0);
            evts[b] = -1;
        }
        for (int t = 0; t < 30; ++t) {
            for (int b = 0; b < V4C_NB; ++b)
                if (((t + b) % 3) == 0) evts[b] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        long nz = 0, z = 0;
        for (int a = 0; a < V4C_NB; ++a)
            for (int b = a + 1; b < V4C_NB; ++b)
                if (net.r[a][b] != 0) nz++;
                else z++;
        bool nonuni = (nz > 0 && z > 0);
        snprintf(buf, 256, "dolu=%ld bos=%ld", nz, z);
        check("P-nonuniform", nonuni, buf);
    }

    // S1 max-not-sum: X guclu-B + zayif-C iliskisinde surum == r_XB
    // (toplam DEGIL) ve argmax == B (mekanizma).
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], false, false, false);
            evts[b] = -1;
        }
        mksig(sigs[0], true, true, false);  // X
        mksig(sigs[1], true, true, false);  // B (X ile ayni)
        mksig(sigs[2], true, true, false);  // C (X ile ayni)
        for (int t = 0; t < 20; ++t) {      // faz1: X-B guclenir (~0.93)
            evts[0] = t;
            evts[1] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        for (int t = 20; t < 23; ++t) {     // faz2: X-C zayif (~0.33)
            evts[0] = t;
            evts[2] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        bool pspk[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) pspk[b] = true;
        int top = -2;
        fixed_t rel = v4c_branch_rel(net, sigs, pspk, 0, top);
        bool ok = (top == 1) && (rel == net.r[0][1]) &&
                  (rel < net.r[0][1] + net.r[0][2]) && (net.r[0][2] > 0);
        snprintf(buf, 256, "rel=%s rXB=%s rXC=%s top=%d", fx(rel),
                 fx(net.r[0][1]), fx(net.r[0][2]), top);
        check("S1-max-not-sum", ok, buf);
    }

    // S2 ayni-guc partner degisimi: r ayni (1.0), uyum B->C kayar ->
    // argmax B->C doner, siddet ayni kalir (kimlik nedensel).
    {
        V4cK4Net net;
        v4c_net_init(net);
        net.r[0][1] = net.r[1][0] = FIXED_ONE;
        net.r[0][2] = net.r[2][0] = FIXED_ONE;
        bool pspk[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) pspk[b] = true;
        V4cSig sigs[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) mksig(sigs[b], false, true, true);
        mksig(sigs[0], true, false, false);  // X
        mksig(sigs[1], true, false, false);  // B: X ile uyumlu
        mksig(sigs[2], false, false, true);  // C: uyumsuz (pay 9)
        int topB = -2;
        fixed_t relB = v4c_branch_rel(net, sigs, pspk, 0, topB);
        mksig(sigs[1], false, false, true);  // B artik uyumsuz
        mksig(sigs[2], true, false, false);  // C artik uyumlu
        int topC = -2;
        fixed_t relC = v4c_branch_rel(net, sigs, pspk, 0, topC);
        bool ok = (topB == 1) && (topC == 2) && (relB == relC) &&
                  (relB == FIXED_ONE);
        snprintf(buf, 256, "top=%d->%d rel=%s", topB, topC, fx(relB));
        check("S2-argmax-flip", ok, buf);
    }

    // S3 soma nedenselligi: AYNI S123 (0.9) + salimli K4 -> ates,
    // salimsiz K4 -> sessiz. K4 state somayi belirler.
    {
        V4cUnit ua, ub;
        memset(&ua, 0, sizeof(ua));
        memset(&ub, 0, sizeof(ub));
        v4c_init(ua, 3);
        v4c_init(ub, 3);
        fixed_t s123 = fixed_from_double(0.9);
        // A: K4 salimli (Vg toplami 1.0 -> S4 = 0.125; 1.025 > 1 atesler).
        bool fa = v4c_soma_fire(ua.base, ua.k4, s123,
                                v4c_soma_s4(FIXED_ONE, 0), 50);
        // B: K4 salimsiz (S4 = 0; 0.9 < 1 sessiz).
        bool fb = v4c_soma_fire(ub.base, ub.k4, s123,
                                v4c_soma_s4(0, 0), 50);
        bool ok = fa && !fb;
        snprintf(buf, 256, "ates(salimli)=%d ates(salimsiz)=%d", (int)fa,
                 (int)fb);
        check("S3-soma-nedensellik", ok, buf);
    }

    printf("OZET-LOB-CHECK: %s\n", fails ? "BATTI" : "OK");
    return fails ? 1 : 0;
}
