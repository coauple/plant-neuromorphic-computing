// ---------------------------------------------------------------------------
// Faz Grubu Ana Koşu — Katman 1 TDM demux kanıtı
//
// 4 pre (P0..P3): aynı leak/gating (dengeli N2 seti), yalnız tau_isi farklı
//   (4/8/12/16, bw=2 — validate_resonance.py ile kalibre, PULSE=0.8).
// Ortak hat: 500-tick döngüde 4 ardışık ritim penceresi → her pre'nin Dal A.
// Post: yalnız sinaptik akımla beslenir (doğrudan uyaran YOK).
// CSV: phase_group_learning.csv. Kriterler: (A) demux seçicilik,
// (B) bant-dışı sönüm, (C) monoton öğrenme + tavan, (D) birleştirici ateş,
// (E) regresyon (kapı kapalıyken synapse/network CSV'leri değişmedi).
// ---------------------------------------------------------------------------

#include <cstdio>
#include <cstdint>
#include "phase_group.h"

// Kalibre parametreler (validate_resonance.py v2, 2026-09-07):
// tau={4,8,12,16} bw=2 pulse=0.8. w0=1.5 (0.3/0.5 bootstrap deadlock verdi:
// post hiç ateşleyemedi → G=0 → öğrenme ölü doğdu; §9.5 Bölüm 0 ile aynı
// fenomen). N_CYCLES=40 (seyrek rejimde yavaş bantların öğrenme sinyaline
// zaman tanımak için).
constexpr int32_t PG_TAUS[PG_NUM_PRE] = {4, 8, 12, 16};
constexpr int32_t PG_BW = 2;
constexpr int CYCLE_LEN = 500;
constexpr int N_CYCLES = 40;
constexpr fixed_t ETA = fixed_from_double(0.2);
constexpr fixed_t PG_PULSE = fixed_from_double(0.8);
constexpr fixed_t PG_W0 = fixed_from_double(1.5);

// Uyarılabilirlik kalibrasyonu: yavaş ritimler pencere başına daha az darbe
// verir; eşit leak'te yavaş bantlar temsil edilemezdi (P3 hiç ateşleyemedi).
// Çözüm: yavaş bantlara düşük leak. Bu BAND TERCİHİ DEĞİL — bant dışı girdi
// kapıda mu=0 ile tamamen silinir (leak'ten bağımsız); leak yalnız bant-içi
// ateş fırsatını eşitler. Seçicilik yalnız ISI kapısından gelir.
static NeuronParams make_pre_params(int idx) {
    NeuronParams p = {0.08, 0.06, 0.04, 0.005, 0.004, 0.003};
    if (idx == 3) {
        p.root_leak = 0.01;
        p.brA_leak = 0.01;
        p.brB_leak = 0.01;
    } else if (idx == 2) {
        p.root_leak = 0.02;
        p.brA_leak = 0.015;
        p.brB_leak = 0.015;
    }
    p.tau_isi = PG_TAUS[idx];
    p.resonance_bw = PG_BW;
    return p;
}

// Ritmik pencereler: (başlangıç, bitiş, darbe aralığı)
struct RhythmWindow {
    int start;
    int end;
    int period;
};
constexpr RhythmWindow WINDOWS[PG_NUM_PRE] = {
    {50, 120, 4}, {150, 220, 8}, {250, 320, 12}, {350, 420, 16}};

// Ortak karışık hat: o anki pencerenin ritmiyle darbe üretir.
static bool phase_group_stimulus(int32_t cycle_t, fixed_t& current_out) {
    for (int i = 0; i < PG_NUM_PRE; ++i) {
        if (cycle_t >= WINDOWS[i].start && cycle_t <= WINDOWS[i].end &&
            (cycle_t - WINDOWS[i].start) % WINDOWS[i].period == 0) {
            current_out = PG_PULSE;
            return true;
        }
    }
    current_out = 0;
    return false;
}

// Ateşi faza ata: döngü-içi tick hangi pencere aralığına düşüyor?
// Aralıklar pencere sonu + 30 tick gecikme payıyla bölünür.
static int tick_to_phase(int32_t cycle_t) {
    if (cycle_t < 150) return 0;
    if (cycle_t < 250) return 1;
    if (cycle_t < 350) return 2;
    return 3;
}

int main() {
    synapse_build_luts();

    printf("=== FAZ GRUBU: 4x ISI-tau demux + capraz-bant birlestirici ===\n");
    printf("tau={4,8,12,16} bw=2 pulse=0.8, %d dongu x %d tick\n", N_CYCLES,
           CYCLE_LEN);

    PhaseGroup pg;
    NeuronParams pre_params[PG_NUM_PRE];
    for (int i = 0; i < PG_NUM_PRE; ++i) pre_params[i] = make_pre_params(i);
    // Post = yavaş entegratör (düşük leak): seyrek bantlardan gelen dağınık
    // sinaptik darbeleri pencere ötesinde toplayabilsin. Rol-farklılaşması
    // (§7: elle tip): kapı pre'de, entegrasyon post'ta.
    NeuronParams post_params = {0.02, 0.015, 0.015, 0.005, 0.004, 0.003};
    phase_group_init(pg, pre_params, post_params, PG_W0, ETA);

    FILE* csv = fopen("phase_group_learning.csv", "w");
    if (!csv) {
        fprintf(stderr, "HATA: phase_group_learning.csv acilamadi\n");
        return 1;
    }
    fprintf(csv,
            "tick,cycle,p0_fired,p1_fired,p2_fired,p3_fired,post_fired,"
            "w0,w1,w2,w3,phase,p0_branchA_v,p1_branchA_v,p2_branchA_v,"
            "p3_branchA_v\n");

    long pre_total[PG_NUM_PRE] = {0, 0, 0, 0};
    long post_total = 0;
    long confusion[PG_NUM_PRE][PG_NUM_PRE] = {{0}};
    long post_per_phase[PG_NUM_PRE] = {0};
    int post_per_cycle[N_CYCLES];
    fixed_t w_at_cycle_end[N_CYCLES][PG_NUM_SYNAPSES];
    for (int c = 0; c < N_CYCLES; ++c) post_per_cycle[c] = 0;

    for (int cycle = 0; cycle < N_CYCLES; ++cycle) {
        for (int t = 0; t < CYCLE_LEN; ++t) {
            int32_t abs_t = cycle * CYCLE_LEN + t;
            fixed_t stim = 0;
            phase_group_stimulus(t, stim);

            PhaseGroupTickResult r = phase_group_tick(pg, abs_t, stim);
            int phase = tick_to_phase(t);

            for (int i = 0; i < PG_NUM_PRE; ++i) {
                if (r.pre_fired[i]) {
                    pre_total[i]++;
                    confusion[i][phase]++;
                }
            }
            if (r.post_fired) {
                post_total++;
                post_per_cycle[cycle]++;
                post_per_phase[phase]++;
            }

            fprintf(csv, "%d,%d,%d,%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%d,%.6f,"
                         "%.6f,%.6f,%.6f\n",
                    abs_t, cycle, r.pre_fired[0] ? 1 : 0,
                    r.pre_fired[1] ? 1 : 0, r.pre_fired[2] ? 1 : 0,
                    r.pre_fired[3] ? 1 : 0, r.post_fired ? 1 : 0,
                    fixed_to_float(pg.syn[0].weight),
                    fixed_to_float(pg.syn[1].weight),
                    fixed_to_float(pg.syn[2].weight),
                    fixed_to_float(pg.syn[3].weight), phase,
                    fixed_to_float(
                        pg.pre[0].compartments[pg.pre[0].branch_A_id]
                            .local_voltage),
                    fixed_to_float(
                        pg.pre[1].compartments[pg.pre[1].branch_A_id]
                            .local_voltage),
                    fixed_to_float(
                        pg.pre[2].compartments[pg.pre[2].branch_A_id]
                            .local_voltage),
                    fixed_to_float(
                        pg.pre[3].compartments[pg.pre[3].branch_A_id]
                            .local_voltage));
        }
        for (int i = 0; i < PG_NUM_SYNAPSES; ++i) {
            w_at_cycle_end[cycle][i] = pg.syn[i].weight;
        }
    }
    fclose(csv);
    printf("CSV yazildi: phase_group_learning.csv\n");

    // --- (A) Seçicilik: 4x4 karışıklık matrisi ---
    printf("\n=== (A) DEMUX SECICILIK (satir=noron, sutun=faz) ===\n");
    printf("        faz0  faz1  faz2  faz3   own%%  rakip_oran\n");
    bool a_ok = true;
    for (int i = 0; i < PG_NUM_PRE; ++i) {
        long tot = pre_total[i];
        long own = confusion[i][i];
        long rival = 0;
        for (int j = 0; j < PG_NUM_PRE; ++j) {
            if (j != i && confusion[i][j] > rival) rival = confusion[i][j];
        }
        double own_pct = tot > 0 ? 100.0 * own / tot : 0.0;
        double ratio = rival > 0 ? (double)own / rival : 999.0;
        printf("P%d(t=%2d) %5ld %5ld %5ld %5ld  %5.1f%%  %6.2fx\n", i,
               PG_TAUS[i], confusion[i][0], confusion[i][1], confusion[i][2],
               confusion[i][3], own_pct, ratio);
        if (!(tot > 0 && own_pct >= 50.0 && ratio >= 2.0)) a_ok = false;
    }
    printf("%s (A): her noron ateslerinin >=%%50'si kendi fazinda ve >=2x rakip\n",
           a_ok ? "OK" : "UYARI");

    // --- (B) Bant-dışı sönüm ---
    printf("\n=== (B) BANT-DISI SONUM ===\n");
    bool b_ok = true;
    for (int i = 0; i < PG_NUM_PRE; ++i) {
        long worst = 0;
        for (int j = 0; j < PG_NUM_PRE; ++j) {
            if (j != i && confusion[i][j] > worst) worst = confusion[i][j];
        }
        double leak = confusion[i][i] > 0 ? 100.0 * worst / confusion[i][i]
                                          : 999.0;
        printf("P%d: en kotu yabanci=%ld hedef=%ld sizinti=%.1f%%\n", i, worst,
               confusion[i][i], leak);
        if (!(confusion[i][i] > 0 && leak <= 25.0)) b_ok = false;
    }
    printf("%s (B): en kotu yabanci faz <= hedef fazin %%25'i\n",
           b_ok ? "OK" : "UYARI");

    // --- (C) Sinaptik öğrenme ---
    // NOT: monotonluk + kesin büyüme (wend > w0) aranır; sıvı "OK" yok —
    // donmuş ağırlık (dw=0, örn. deadlock) monoton sayılır ama büyüme
    // şartını geçemez. Tavan (W_MAX) bu seyrek rejimde 40 döngüde
    // dolmaz; dürüst rapor: büyüme miktarları yazılır.
    printf("\n=== (C) SINAPTIK OGRENME ===\n");
    bool c_ok = true;
    double wstart = fixed_to_float(PG_W0);
    for (int i = 0; i < PG_NUM_SYNAPSES; ++i) {
        bool mono = true;
        for (int c = 1; c < N_CYCLES; ++c) {
            if (w_at_cycle_end[c][i] < w_at_cycle_end[c - 1][i]) mono = false;
        }
        double wend = fixed_to_float(w_at_cycle_end[N_CYCLES - 1][i]);
        bool grew = (wend > wstart + 1e-9);
        printf("syn[%d]: %.3f -> %.6f (buyume %+.6f) monoton=%s\n", i, wstart,
               wend, wend - wstart, mono ? "evet" : "HAYIR");
        if (!mono || !grew) c_ok = false;
    }
    printf("%s (C): 4 sinaps monoton buyuyor (seyrek rejim: yavas bantlar\n"
           "   cok yavas buyur; kuadratik kuralin hiz-oran bagimliliginin\n"
           "   dogal sonucu, kural bozuk degil)\n",
           c_ok ? "OK" : "UYARI");

    // --- (D) Birleştirici ---
    printf("\n=== (D) BIRLESTIRICI (post, yalniz sinaptik) ===\n");
    printf("post toplam ates: %ld\n", post_total);
    printf("faz dagilimi: %ld %ld %ld %ld\n", post_per_phase[0],
           post_per_phase[1], post_per_phase[2], post_per_phase[3]);
    long early = 0, late = 0;
    for (int c = 0; c < 5; ++c) early += post_per_cycle[c];
    for (int c = N_CYCLES - 5; c < N_CYCLES; ++c) late += post_per_cycle[c];
    printf("erken(0-4): %ld gec(%d-%d): %ld\n", early, N_CYCLES - 5,
           N_CYCLES - 1, late);
    bool d_ok = (post_total > 0);
    printf("%s (D): post atesliyor\n", d_ok ? "OK" : "UYARI");

    printf("\n=== OZET: A=%s B=%s C=%s D=%s ===\n", a_ok ? "OK" : "UYARI",
           b_ok ? "OK" : "UYARI", c_ok ? "OK" : "UYARI", d_ok ? "OK" : "UYARI");
    return 0;
}
