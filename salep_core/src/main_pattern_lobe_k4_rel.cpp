// ---------------------------------------------------------------------------
// K4 SENTETIK ILISKI TESTLERI — R1-R8 (REV4, additive, YENI dosya).
//
// Afferent/kablo YOK: imzalar + olay saatleri sentetik kurulur,
// v4c_net_update / v4c_branch_rel dogrudan surulur. Kapilar:
//   R1 ayni imza + ayni pencere -> r >= 0.8 (20 tick)
//   R2 farkli pencere (doldur 20 + ayir 25) -> r <= 0.1
//   R3 farkli kimlik + ayni pencere -> r <= 0.1 (20 tick)
//   R4 marj: R1_final - max(R2,R3) >= 0.6
//   R5 kombinasyon imzalari A+B / A+C / B+D / A+C+D -> 4 ayri imza
//      (ikili pay<18, yani birebir degil)
//   R6 ortak-mod: karisik kimlik + global coincidence -> capraz ciftler
//      zayif (r <= 0.1), eslesen cift guclu (r >= 0.8)
//      (kod kumesi 000/011/110: capraz pay 12 < 13 -> kapali)
//   R7 seyrek/ufak oruntu: esleseni olmayan zayif dal rel ~= 0, top=-1;
//      esleseni olan zayif dal rel > 0.1 (max-secimi)
//   R8 spike-kapisi: r yuksek + uyum acik olsa bile partner spike'i yoksa
//      surum 0 (top=-1); spike varsa surum r (top=partner)
// Cikti: OZET-K4-REL: R1..R8 + cikis kodu.
// ---------------------------------------------------------------------------

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

static void mksig(V4cSig& s, bool k1, bool k2, bool k3) {
    V4cIdentity id;
    fixed_t hi = GATING_ACTIVATE_THRESH + fixed_from_double(0.5);
    id.v[0] = k1 ? hi : V_REST;
    id.v[1] = k2 ? hi : V_REST;
    id.v[2] = k3 ? hi : V_REST;
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

    fixed_t r1 = 0, r2 = 0, r3 = 0;

    // R1: ayni imza + ayni pencere (bid 0,1; pay 18).
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
        mksig(sigs[1], true, true, false);
        for (int t = 0; t < 20; ++t) {
            evts[0] = t;
            evts[1] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        r1 = net.r[0][1];
        snprintf(buf, 256, "r=%s", fx(r1));
        check("R1-ayni-kimlik-pencere", r1 >= fixed_from_double(0.8), buf);
    }

    // R2: doldur 20 + ayir 25 (bid 2,3).
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], true, false, true);
            evts[b] = -1;
        }
        for (int t = 0; t < 20; ++t) {
            evts[2] = t;
            evts[3] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        // Pencere-eskimesi (10) + bozunum (25): 3 susar.
        for (int t = 20; t < 55; ++t) {
            evts[2] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        r2 = net.r[2][3];
        snprintf(buf, 256, "r=%s", fx(r2));
        check("R2-farkli-pencere", r2 <= fixed_from_double(0.1), buf);
    }

    // R3: farkli kimlik + ayni pencere (bid 4,5: pay 12 < 13).
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], false, false, false);
            evts[b] = -1;
        }
        mksig(sigs[4], true, true, true);
        mksig(sigs[5], true, false, false);
        for (int t = 0; t < 20; ++t) {
            evts[4] = t;
            evts[5] = t;
            v4c_net_update(net, sigs, evts, t);
        }
        r3 = net.r[4][5];
        snprintf(buf, 256, "r=%s pay=%d", fx(r3),
                 v4c_sim_num(sigs[4], sigs[5]));
        check("R3-farkli-kimlik", r3 <= fixed_from_double(0.1), buf);
    }

    // R4 marj.
    {
        fixed_t mx = (r2 > r3) ? r2 : r3;
        bool ok = ((r1 - mx) >= fixed_from_double(0.6));
        snprintf(buf, 256, "marj=%s", fx(r1 - mx));
        check("R4-marj", ok, buf);
    }

    // R5: 4 kombinasyon imzasi pairwise farkli (pay<18).
    {
        V4cSig s[4];
        mksig(s[0], true, true, false);    // A+B
        mksig(s[1], true, false, true);    // A+C
        mksig(s[2], false, true, true);    // B+D (k2,k3 agirlikli)
        mksig(s[3], true, true, true);     // A+B+C (tam)
        bool alldiff = true;
        int mn = 18;
        for (int i = 0; i < 4; ++i)
            for (int j = i + 1; j < 4; ++j) {
                int pay = v4c_sim_num(s[i], s[j]);
                if (pay < mn) mn = pay;
                if (pay >= 18) alldiff = false;
            }
        snprintf(buf, 256, "min-pay=%d", mn);
        check("R5-4-ayri-imza", alldiff, buf);
    }

    // R6 ortak-mod: karisik kimlik + global coincidence.
    // Cift-agirlik kod kumesi (000/011/110): capraz pay 12 < 13 -> kapali.
    {
        V4cK4Net net;
        v4c_net_init(net);
        V4cSig sigs[V4C_NB];
        int32_t evts[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigs[b], false, false, false);
            evts[b] = -1;
        }
        mksig(sigs[10], true, true, false);
        mksig(sigs[11], true, true, false);  // eslesen cift (pay 18)
        mksig(sigs[12], false, false, false);  // 000
        mksig(sigs[13], false, true, true);    // 011
        for (int t = 0; t < 20; ++t) {
            evts[10] = evts[11] = evts[12] = evts[13] = t;  // global coin
            v4c_net_update(net, sigs, evts, t);
        }
        fixed_t cross = net.r[10][12];
        if (net.r[10][13] > cross) cross = net.r[10][13];
        if (net.r[12][13] > cross) cross = net.r[12][13];
        bool ok = (net.r[10][11] >= fixed_from_double(0.8)) &&
                  (cross <= fixed_from_double(0.1));
        snprintf(buf, 256, "eslesen=%s capraz-max=%s", fx(net.r[10][11]),
                 fx(cross));
        check("R6-ortak-mod", ok, buf);
    }

    // R7 seyrek/ufak: zayif dal; eslesensiz rel~=0 (top=-1), eslesenli
    // rel>0.1 (max-secimi).
    {
        // Durum A: bid 20 zayif kimlikte (pay 9 < 13), digerleri farkli.
        V4cK4Net na;
        v4c_net_init(na);
        V4cSig siga[V4C_NB];
        int32_t eva[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(siga[b], false, true, true);
            eva[b] = -1;
        }
        mksig(siga[20], true, false, false);
        for (int t = 0; t < 30; ++t) {
            for (int b = 0; b < V4C_NB; ++b) eva[b] = t;
            v4c_net_update(na, siga, eva, t);
        }
        bool pa[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) pa[b] = true;
        int topA = -2;
        fixed_t relA = v4c_branch_rel(na, siga, pa, 20, topA);
        // Durum B: bid 21 ayni zayif kimlikte, 20 ile coincident.
        V4cK4Net nb;
        v4c_net_init(nb);
        V4cSig sigb[V4C_NB];
        int32_t evb[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            mksig(sigb[b], false, true, true);
            evb[b] = -1;
        }
        mksig(sigb[20], true, false, false);
        mksig(sigb[21], true, false, false);
        for (int t = 0; t < 30; ++t) {
            for (int b = 0; b < V4C_NB; ++b) evb[b] = t;
            v4c_net_update(nb, sigb, evb, t);
        }
        bool pb[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) pb[b] = true;
        int topB = -2;
        fixed_t relB = v4c_branch_rel(nb, sigb, pb, 20, topB);
        bool ok = (relA <= fixed_from_double(0.01)) && (topA == -1) &&
                  (relB > fixed_from_double(0.1)) && (topB == 21);
        snprintf(buf, 256, "rel_eslesensiz=%s(top=%d) rel_eslesenli=%s(top=%d)",
                 fx(relA), topA, fx(relB), topB);
        check("R7-seyrek-destek", ok, buf);
    }

    // R8 spike-kapisi: r=1 + uyum acik; spike yoksa surum 0, spike varsa r.
    {
        V4cK4Net net;
        v4c_net_init(net);
        net.r[30][31] = net.r[31][30] = FIXED_ONE;
        V4cSig sigs[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) mksig(sigs[b], false, true, true);
        mksig(sigs[30], true, false, false);
        mksig(sigs[31], true, false, false);  // uyum acik (pay 18)
        bool p0[V4C_NB], p1[V4C_NB];
        for (int b = 0; b < V4C_NB; ++b) {
            p0[b] = false;  // 31 spike'siz
            p1[b] = (b == 31);  // yalniz 31 spike'li
        }
        int t0 = -2, t1 = -2;
        fixed_t r0 = v4c_branch_rel(net, sigs, p0, 30, t0);
        fixed_t r1x = v4c_branch_rel(net, sigs, p1, 30, t1);
        bool ok = (r0 == 0) && (t0 == -1) && (r1x == FIXED_ONE) &&
                  (t1 == 31);
        snprintf(buf, 256, "surum(spikesiz)=%s surum(spikeli)=%s top=%d",
                 fx(r0), fx(r1x), t1);
        check("R8-spike-kapisi", ok, buf);
    }

    printf("OZET-K4-REL: %s\n", fails ? "BATTI" : "R1 R2 R3 R4 R5 R6 R7 R8");
    return fails ? 1 : 0;
}
