#ifndef PHASE_GROUP_H
#define PHASE_GROUP_H

#include "neuron.h"
#include "synapse.h"

// ---------------------------------------------------------------------------
// Faz Grubu — Katman 1 TDM demux kanıtı (ardışık-pencere, simultane FDM değil)
//
// Topoloji: 4 presinaptik nöron (P0..P3, yalnız tau_isi farklı: 4/8/12/16,
// hepsi aynı leak/gating seti → seçicilik yalnız ISI kapısından gelir)
// → post (birleştirici) Dal A. 4 sinaps, w0=0.3 bootstrap (§9.5 tecrübesi).
//
// SAPMA NOTU (anayasa §3): Dal B bu testte BOŞ. Coincidence mekanizması bu
// testin konusu değil (branch/network'te kanıtlandı); saf birikim +
// rezonans seçiciliği izole ölçülür. Soma bonusu devreye girmez.
// ---------------------------------------------------------------------------

constexpr int PG_NUM_PRE      = 4;
constexpr int PG_NUM_SYNAPSES = 4;

struct PhaseGroup {
    DendriticNeuron pre[PG_NUM_PRE];
    DendriticNeuron post;

    Synapse syn[PG_NUM_SYNAPSES];  // syn[i] = P[i] -> post Dal A

    SpikeRateCounter rc_pre[PG_NUM_SYNAPSES];
    SpikeRateCounter rc_post[PG_NUM_SYNAPSES];

    fixed_t eta;
};

inline void phase_group_init(PhaseGroup& pg,
                             const NeuronParams pre_params[PG_NUM_PRE],
                             const NeuronParams& post_params,
                             fixed_t initial_w,
                             fixed_t eta) {
    for (int i = 0; i < PG_NUM_PRE; ++i) {
        neuron_init_with_params(pg.pre[i], i, pre_params[i]);
    }
    neuron_init_with_params(pg.post, PG_NUM_PRE, post_params);

    for (int i = 0; i < PG_NUM_SYNAPSES; ++i) {
        synapse_init(pg.syn[i], i, pg.post.branch_A_id, initial_w);
    }

    for (int i = 0; i < PG_NUM_SYNAPSES; ++i) {
        rate_counter_init(pg.rc_pre[i]);
        rate_counter_init(pg.rc_post[i]);
    }

    pg.eta = eta;
}

struct PhaseGroupTickResult {
    bool pre_fired[PG_NUM_PRE];
    bool post_fired;
};

// Tick sırası (network_tick disiplini, §9.5):
//   1) stimulus>0 ise her pre'nin YALNIZ Dal A'sına enjekte et (Dal B boş)
//   2) pre'leri tick'le (P0..P3 sırayla)
//   3) ateşleyen her pre için I_syn = w*0.5'i post Dal A'ya enjekte et
//   4) post'u tick'le (post'a doğrudan uyaran YOK — yalnız sinaptik)
//   5) rate counter + öğrenme (her syn bağımsız)
inline PhaseGroupTickResult phase_group_tick(PhaseGroup& pg, int32_t t,
                                             fixed_t stimulus) {
    PhaseGroupTickResult result;

    // --- 1) Ortak karışık hat → her pre'nin Dal A'sı ---
    if (stimulus > 0) {
        for (int i = 0; i < PG_NUM_PRE; ++i) {
            neuron_inject_current(pg.pre[i], pg.pre[i].branch_A_id, stimulus, t);
        }
    }

    // --- 2) Presinaptik tick ---
    for (int i = 0; i < PG_NUM_PRE; ++i) {
        result.pre_fired[i] = neuron_tick(pg.pre[i], t);
    }

    // --- 3) Sinaptik aktarım ---
    for (int i = 0; i < PG_NUM_SYNAPSES; ++i) {
        int src = pg.syn[i].source_neuron_id;
        if (result.pre_fired[src]) {
            fixed_t cur = synapse_transmission_current(pg.syn[i]);
            neuron_inject_current(pg.post, pg.syn[i].target_compartment_id,
                                  cur, t);
        }
    }

    // --- 4) Post tick ---
    result.post_fired = neuron_tick(pg.post, t);

    // --- 5) Öğrenme ---
    for (int i = 0; i < PG_NUM_SYNAPSES; ++i) {
        int src = pg.syn[i].source_neuron_id;
        rate_counter_update(pg.rc_pre[i], result.pre_fired[src]);
        rate_counter_update(pg.rc_post[i], result.post_fired);
        synapse_apply_learning(pg.syn[i], pg.rc_pre[i].count,
                               pg.rc_post[i].count, pg.eta);
    }

    return result;
}

#endif  // PHASE_GROUP_H
