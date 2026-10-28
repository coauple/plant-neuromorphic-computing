#ifndef CAUSALITY_H
#define CAUSALITY_H

#include "neuron.h"
#include "synapse.h"

// ---------------------------------------------------------------------------
// Nedensellik koprusu — Katman 1 demux + coincidence + kuadratik ogrenme
//
// Topoloji: 4 pre (P0..P3, tau_isi=4/8/12/16, bw=2) + 1 target.
//   s0 = P0 -> target Dal A ; s1 = P1 -> target Dal A
//   s2 = P2 -> target Dal B ; s3 = P3 -> target Dal B
// P1/P3 negatif kontrol: uyarilmazlar -> ateslemezler -> dw=0 beklenir.
//
// DURUST NOT (TDM siniri): ISI kapisi tek ISI olcer; Faz 3'te iki ritim
// tek telde degil, pre-bazli (P0'a 4'luk, P2'ye 12'lik, senkron baslangic)
// verilir. Dal A = faz hatti, Dal B = olay hatti kullanimidir; target
// seviyesinde iki dal zaten ayri sinaptik hattir.
// ---------------------------------------------------------------------------

constexpr int CAUS_NUM_PRE      = 4;
constexpr int CAUS_NUM_SYNAPSES = 4;

struct CausalityNetwork {
    DendriticNeuron pre[CAUS_NUM_PRE];
    DendriticNeuron target;

    Synapse syn[CAUS_NUM_SYNAPSES];

    SpikeRateCounter rc_pre[CAUS_NUM_SYNAPSES];
    SpikeRateCounter rc_post[CAUS_NUM_SYNAPSES];

    fixed_t eta;
};

inline void causality_init(CausalityNetwork& cn,
                           const NeuronParams pre_params[CAUS_NUM_PRE],
                           const NeuronParams& target_params,
                           fixed_t initial_w,
                           fixed_t eta) {
    for (int i = 0; i < CAUS_NUM_PRE; ++i) {
        neuron_init_with_params(cn.pre[i], i, pre_params[i]);
    }
    neuron_init_with_params(cn.target, CAUS_NUM_PRE, target_params);

    synapse_init(cn.syn[0], 0, cn.target.branch_A_id, initial_w);
    synapse_init(cn.syn[1], 1, cn.target.branch_A_id, initial_w);
    synapse_init(cn.syn[2], 2, cn.target.branch_B_id, initial_w);
    synapse_init(cn.syn[3], 3, cn.target.branch_B_id, initial_w);

    for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
        rate_counter_init(cn.rc_pre[i]);
        rate_counter_init(cn.rc_post[i]);
    }

    cn.eta = eta;
}

struct CausalityTickResult {
    bool pre_fired[CAUS_NUM_PRE];
    bool target_fired;
};

// Tick sirasi (phase_group_tick disiplini):
//   1) stim_pre[i]>0 ise pre[i] Dal A'ya enjekte et (pre-bazli, Dal B bos)
//   2) pre tick  3) atesleyen pre -> I_syn hedef dala  4) target tick
//      (target'a dogrudan uyaran YOK)  5) rate counter + ogrenme.
// stimulus: faz programindan gelen, pre basina akim (0 = uyaran yok).
inline CausalityTickResult causality_tick(CausalityNetwork& cn, int32_t t,
                                          const fixed_t stimulus[CAUS_NUM_PRE],
                                          fixed_t dw_out[CAUS_NUM_SYNAPSES]) {
    CausalityTickResult result;

    // --- 1) Pre-bazli uyaran ---
    for (int i = 0; i < CAUS_NUM_PRE; ++i) {
        if (stimulus[i] > 0) {
            neuron_inject_current(cn.pre[i], cn.pre[i].branch_A_id,
                                  stimulus[i], t);
        }
    }

    // --- 2) Pre tick ---
    for (int i = 0; i < CAUS_NUM_PRE; ++i) {
        result.pre_fired[i] = neuron_tick(cn.pre[i], t);
    }

    // --- 3) Sinaptik aktarim ---
    for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
        int src = cn.syn[i].source_neuron_id;
        if (result.pre_fired[src]) {
            fixed_t cur = synapse_transmission_current(cn.syn[i]);
            neuron_inject_current(cn.target, cn.syn[i].target_compartment_id,
                                  cur, t);
        }
    }

    // --- 4) Target tick ---
    result.target_fired = neuron_tick(cn.target, t);

    // --- 5) Ogrenme (dw_out: o tick'in dw'si, CSV/rapor icin) ---
    for (int i = 0; i < CAUS_NUM_SYNAPSES; ++i) {
        int src = cn.syn[i].source_neuron_id;
        rate_counter_update(cn.rc_pre[i], result.pre_fired[src]);
        rate_counter_update(cn.rc_post[i], result.target_fired);
        dw_out[i] = synapse_apply_learning(cn.syn[i], cn.rc_pre[i].count,
                                           cn.rc_post[i].count, cn.eta);
    }

    return result;
}

// Target'in iki dalinin da ayni pencerede girdi alip almadigi (CSV icin).
inline bool causality_has_coincidence(const CausalityNetwork& cn, int32_t t) {
    bool branch_A_input =
        (cn.target.branch_A_last_input_tick >= 0) &&
        ((t - cn.target.branch_A_last_input_tick) <= COINCIDENCE_WINDOW_MS);
    bool branch_B_input =
        (cn.target.branch_B_last_input_tick >= 0) &&
        ((t - cn.target.branch_B_last_input_tick) <= COINCIDENCE_WINDOW_MS);
    return branch_A_input && branch_B_input;
}

#endif  // CAUSALITY_H
