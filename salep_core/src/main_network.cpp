// ---------------------------------------------------------------------------
// Katman 1 Ağ Testi — CLAUDE.md §9.5
//
// Topoloji: N0 (hızlı) ve N1 (yavaş) -> N3 Dal A (multiplex),
//           N2 (dengeli) -> N3 Dal B.
// Bölüm 0: w=0.05 (bootstrap deadlock) demo, konsol-only, CSV yok.
// Ana koşu: w0=0.3, 20 döngü x 500 tick = 10.000 tick, network_learning.csv.
// ---------------------------------------------------------------------------

#include <cstdio>
#include <cstdint>
#include "network.h"

constexpr int CYCLE_LEN = 500;
constexpr int N_CYCLES  = 20;
constexpr fixed_t ETA   = fixed_from_double(0.2);

// main_multi.cpp NEURON_TYPES ile birebir aynı
const NeuronParams N0_PARAMS = {0.02, 0.015, 0.015, 0.03, 0.035, 0.03};   // hizli ritim
const NeuronParams N1_PARAMS = {0.20, 0.18,  0.15,  0.001, 0.001, 0.001}; // yavas ritim
const NeuronParams N2_PARAMS = {0.08, 0.06,  0.04,  0.005, 0.004, 0.003}; // dengeli
const NeuronParams N3_PARAMS = N2_PARAMS;                                 // dengeli (post)

// main_multi.cpp / main_synapse.cpp should_inject ile birebir aynı
bool should_inject(int32_t cycle_t, fixed_t& current_out) {
    if (cycle_t >= 50 && cycle_t <= 80 && (cycle_t - 50) % 5 == 0) {
        current_out = fixed_from_double(0.5);
        return true;
    }
    if (cycle_t >= 150 && cycle_t <= 180 && (cycle_t - 150) % 3 == 0) {
        current_out = fixed_from_double(0.8);
        return true;
    }
    if (cycle_t >= 220 && cycle_t <= 250 && (cycle_t - 220) % 5 == 0) {
        current_out = fixed_from_double(0.5);
        return true;
    }
    current_out = 0;
    return false;
}

// ---------------------------------------------------------------------------
// Bölüm 0 — Bootstrap deadlock demo (konsol-only, CSV yok)
//
// w=0.05 ile I_syn = 0.05*0.5 = 0.025 -- N3'ü asla ateşletemez (bkz. §9.4
// T1: w=0.05 -> I=0.025, N1 ateş=0). 3 dongu (1500 tick) calistirilir,
// N3 hic ateslenmemeli ve syn agirliklari duz kalmali (ogrenme sinyali
// r_post=0 oldugu icin G=0 -> dw=0).
// ---------------------------------------------------------------------------

void run_deadlock_demo() {
    printf("\n=== BOLUM 0: BOOTSTRAP DEADLOCK DEMO (w=0.05, 3 dongu, CSV yok) ===\n");

    Network net;
    NeuronParams pre_params[NET_NUM_PRE] = {N0_PARAMS, N1_PARAMS, N2_PARAMS};
    fixed_t w0 = fixed_from_double(0.05);
    network_init(net, pre_params, N3_PARAMS, w0, ETA);

    int n3_fires = 0;
    fixed_t w_start[NET_NUM_SYNAPSES];
    for (int i = 0; i < NET_NUM_SYNAPSES; ++i) w_start[i] = net.syn[i].weight;

    for (int cycle = 0; cycle < 3; ++cycle) {
        for (int t = 0; t < CYCLE_LEN; ++t) {
            int32_t abs_t = cycle * CYCLE_LEN + t;
            fixed_t stim = 0;
            should_inject(t, stim);
            NetworkTickResult r = network_tick(net, abs_t, stim);
            if (r.post_fired) n3_fires++;
        }
    }

    printf("N3 ates sayisi (1500 tick): %d\n", n3_fires);
    for (int i = 0; i < NET_NUM_SYNAPSES; ++i) {
        printf("syn[%d] weight: %.6f -> %.6f\n", i,
               fixed_to_float(w_start[i]), fixed_to_float(net.syn[i].weight));
    }

    if (n3_fires == 0) {
        printf("OK DOGRULANDI: N3 deadlock durumunda hic atesenmedi (dusuk w -> yetersiz akim).\n");
    } else {
        printf("UYARI: N3 deadlock durumunda beklenmedik sekilde atesenmis (%d kez).\n", n3_fires);
    }
}

int main() {
    synapse_build_luts();

    run_deadlock_demo();

    printf("\n=== ANA KOSU: w0=0.3, %d dongu x %d tick = %d tick ===\n",
           N_CYCLES, CYCLE_LEN, N_CYCLES * CYCLE_LEN);

    Network net;
    NeuronParams pre_params[NET_NUM_PRE] = {N0_PARAMS, N1_PARAMS, N2_PARAMS};
    fixed_t w0 = fixed_from_double(0.3);
    network_init(net, pre_params, N3_PARAMS, w0, ETA);

    FILE* csv = fopen("network_learning.csv", "w");
    if (!csv) {
        fprintf(stderr, "HATA: network_learning.csv acilamadi\n");
        return 1;
    }
    fprintf(csv, "tick,cycle,n0_fired,n1_fired,n2_fired,n3_fired,w0,w1,w2,coincidence,"
                 "n3_root_v,n3_branchA_v,n3_branchB_v,n3_soma_v\n");

    // --- İstatistik biriktiriciler ---
    long total_n0 = 0, total_n1 = 0, total_n2 = 0, total_n3 = 0;

    // (A) Sinaps monotonluk takibi: her döngü sonu ağırlık
    fixed_t w_at_cycle_end[N_CYCLES][NET_NUM_SYNAPSES];

    // (B) N3 döngü başına ateş sayısı
    int n3_fires_per_cycle[N_CYCLES];
    for (int c = 0; c < N_CYCLES; ++c) n3_fires_per_cycle[c] = 0;

    // (C) Dal A multiplex korelasyon sayaçları
    long only_n0 = 0, only_n1 = 0, both_n0_n1 = 0, neither = 0;
    long n3_fire_given_only_n1 = 0, n3_fire_given_both = 0;

    for (int cycle = 0; cycle < N_CYCLES; ++cycle) {
        for (int t = 0; t < CYCLE_LEN; ++t) {
            int32_t abs_t = cycle * CYCLE_LEN + t;
            fixed_t stim = 0;
            should_inject(t, stim);

            NetworkTickResult r = network_tick(net, abs_t, stim);
            bool coincidence = network_has_coincidence(net, abs_t);

            bool n0f = r.pre_fired[0], n1f = r.pre_fired[1], n2f = r.pre_fired[2];
            bool n3f = r.post_fired;

            if (n0f) total_n0++;
            if (n1f) total_n1++;
            if (n2f) total_n2++;
            if (n3f) { total_n3++; n3_fires_per_cycle[cycle]++; }

            // Dal A multiplex korelasyon (N0/N1)
            if (n0f && n1f) {
                both_n0_n1++;
                if (n3f) n3_fire_given_both++;
            } else if (n0f && !n1f) {
                only_n0++;
            } else if (!n0f && n1f) {
                only_n1++;
                if (n3f) n3_fire_given_only_n1++;
            } else {
                neither++;
            }

            fprintf(csv, "%d,%d,%d,%d,%d,%d,%.6f,%.6f,%.6f,%d,%.6f,%.6f,%.6f,%.6f\n",
                    abs_t, cycle,
                    n0f ? 1 : 0, n1f ? 1 : 0, n2f ? 1 : 0, n3f ? 1 : 0,
                    fixed_to_float(net.syn[0].weight),
                    fixed_to_float(net.syn[1].weight),
                    fixed_to_float(net.syn[2].weight),
                    coincidence ? 1 : 0,
                    fixed_to_float(net.post.compartments[net.post.root_compartment_id].local_voltage),
                    fixed_to_float(net.post.compartments[net.post.branch_A_id].local_voltage),
                    fixed_to_float(net.post.compartments[net.post.branch_B_id].local_voltage),
                    fixed_to_float(net.post.soma_voltage));
        }
        for (int i = 0; i < NET_NUM_SYNAPSES; ++i) {
            w_at_cycle_end[cycle][i] = net.syn[i].weight;
        }
    }
    fclose(csv);

    printf("\nToplam N0 ates: %ld\n", total_n0);
    printf("Toplam N1 ates: %ld\n", total_n1);
    printf("Toplam N2 ates: %ld\n", total_n2);
    printf("Toplam N3 ates: %ld\n", total_n3);
    printf("CSV yazildi: network_learning.csv\n");

    // --- (a) BAĞIMSIZ ÖĞRENME: 3 sinaps monotonluk ---
    printf("\n=== (a) BAGIMSIZ OGRENME - 3 SINAPS MONOTONLUK ===\n");
    bool monotonic[NET_NUM_SYNAPSES] = {true, true, true};
    for (int i = 0; i < NET_NUM_SYNAPSES; ++i) {
        for (int c = 1; c < N_CYCLES; ++c) {
            if (fixed_to_float(w_at_cycle_end[c][i]) < fixed_to_float(w_at_cycle_end[c-1][i]) - 1e-5f) {
                monotonic[i] = false;
            }
        }
        printf("syn[%d] dongu sonu agirliklar: baslangic=%.3f dongu0=%.3f dongu%d=%.3f\n",
               i, fixed_to_float(w0), fixed_to_float(w_at_cycle_end[0][i]),
               N_CYCLES - 1, fixed_to_float(w_at_cycle_end[N_CYCLES-1][i]));
    }
    bool all_monotonic = monotonic[0] && monotonic[1] && monotonic[2];
    if (all_monotonic) {
        printf("OK DOGRULANDI: Uc sinaps da monoton artan, tavana ulasiyor.\n");
    } else {
        printf("UYARI: Bir veya daha fazla sinaps monoton artmadi.\n");
    }

    // --- (b) N3 davranışı: erken vs geç ---
    printf("\n=== (b) N3 DAVRANISI DEGISIYOR MU: ERKEN VS GEC ===\n");
    for (int c = 0; c < N_CYCLES; ++c) {
        printf("Dongu %2d: %d ates\n", c, n3_fires_per_cycle[c]);
    }
    int early_window = (N_CYCLES >= 5) ? 5 : N_CYCLES;
    int late_window   = (N_CYCLES >= 5) ? 5 : N_CYCLES;
    long early_sum = 0, late_sum = 0;
    for (int c = 0; c < early_window; ++c) early_sum += n3_fires_per_cycle[c];
    for (int c = N_CYCLES - late_window; c < N_CYCLES; ++c) late_sum += n3_fires_per_cycle[c];
    double ratio = (early_sum > 0) ? (double)late_sum / (double)early_sum : 0.0;
    printf("Erken pencere (dongu 0-%d) toplam: %ld\n", early_window - 1, early_sum);
    printf("Gec pencere (dongu %d-%d) toplam: %ld\n", N_CYCLES - late_window, N_CYCLES - 1, late_sum);
    printf("Oran (gec/erken): %.2fx\n", ratio);
    if (ratio >= 2.0) {
        printf("OK DOGRULANDI: N3 ates hizi erken->gec en az 2x artti.\n");
    } else {
        printf("UYARI: N3 ates hizi erken->gec artisi beklenenden dusuk (%.2fx).\n", ratio);
    }

    // --- (c) Dal A multiplex analizi ---
    printf("\n=== (c) DAL A MULTIPLEX ANALIZI ===\n");
    printf("Sadece N0: %ld tick\n", only_n0);
    printf("Sadece N1: %ld tick\n", only_n1);
    printf("N0+N1 birlikte: %ld tick\n", both_n0_n1);
    printf("Hicbiri: %ld tick\n", neither);
    double rate_only_n1 = (only_n1 > 0) ? (double)n3_fire_given_only_n1 / (double)only_n1 : 0.0;
    double rate_both    = (both_n0_n1 > 0) ? (double)n3_fire_given_both / (double)both_n0_n1 : 0.0;
    printf("Sadece N1 atesi -> N3 ates: %ld/%ld (%.1f%%)\n",
           n3_fire_given_only_n1, only_n1, rate_only_n1 * 100.0);
    printf("N0+N1 birlikte -> N3 ates: %ld/%ld (%.1f%%)\n",
           n3_fire_given_both, both_n0_n1, rate_both * 100.0);
    double amplification = (rate_only_n1 > 0) ? (rate_both / rate_only_n1) : 0.0;
    printf("Multiplex amplifikasyon: %.2fx\n", amplification);
    if (amplification > 1.0) {
        printf("OK DOGRULANDI: Dal A, N0+N1 coincidence ile amplifikasyon gosteriyor.\n");
    } else {
        printf("UYARI: Dal A multiplex amplifikasyonu gozlemlenmedi.\n");
    }

    // --- Özet ---
    printf("\n=== OZET ===\n");
    bool all_ok = all_monotonic && (ratio >= 2.0) && (amplification > 1.0);
    if (all_ok) {
        printf("OK TUM DOGRULMALAR BASARILI!\n");
    } else {
        printf("UYARI: Bazi dogrulmalar basarisiz veya beklenen esigin altinda.\n");
    }

    return 0;
}
