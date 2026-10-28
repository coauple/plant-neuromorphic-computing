#ifndef NETWORK_H
#define NETWORK_H

#include "neuron.h"
#include "synapse.h"

// ---------------------------------------------------------------------------
// Katman 1 ağ testi — 3 presinaptik nöron (N0,N1,N2) + 1 postsinaptik (N3)
//
// CLAUDE.md §9.5: N0 (hızlı) ve N1 (yavaş) → N3 Dal A (multiplex),
// N2 (dengeli) → N3 Dal B. Bölüm 9.4'teki tek-sinaps L0/L1/T1/T2
// altyapısı (SpikeRateCounter, synapse_apply_learning,
// synapse_transmission_current) DEĞİŞTİRİLMEDEN üç sinapsa genişletiliyor.
// ---------------------------------------------------------------------------

constexpr int NET_NUM_PRE      = 3;
constexpr int NET_NUM_SYNAPSES = 3;

struct Network {
    DendriticNeuron pre[NET_NUM_PRE];   // N0, N1, N2
    DendriticNeuron post;               // N3

    Synapse syn[NET_NUM_SYNAPSES];      // syn[0]=N0->A, syn[1]=N1->A, syn[2]=N2->B

    SpikeRateCounter rc_pre[NET_NUM_SYNAPSES];
    SpikeRateCounter rc_post[NET_NUM_SYNAPSES];

    fixed_t eta;
};

inline void network_init(Network& net,
                          const NeuronParams pre_params[NET_NUM_PRE],
                          const NeuronParams& post_params,
                          fixed_t initial_w,
                          fixed_t eta) {
    for (int i = 0; i < NET_NUM_PRE; ++i) {
        neuron_init_with_params(net.pre[i], i, pre_params[i]);
    }
    neuron_init_with_params(net.post, NET_NUM_PRE, post_params);

    // syn[0]: N0 -> post Dal A (branch_A_id)
    synapse_init(net.syn[0], 0, net.post.branch_A_id, initial_w);
    // syn[1]: N1 -> post Dal A (branch_A_id) -- Dal A multiplex/coincidence
    synapse_init(net.syn[1], 1, net.post.branch_A_id, initial_w);
    // syn[2]: N2 -> post Dal B (branch_B_id)
    synapse_init(net.syn[2], 2, net.post.branch_B_id, initial_w);

    for (int i = 0; i < NET_NUM_SYNAPSES; ++i) {
        rate_counter_init(net.rc_pre[i]);
        rate_counter_init(net.rc_post[i]);
    }

    net.eta = eta;
}

struct NetworkTickResult {
    bool pre_fired[NET_NUM_PRE];
    bool post_fired;
};

// Tick sırası (değiştirilmez):
//   1) stimulus>0 ise her pre nörona (Dal A + Dal B) enjekte et
//   2) her pre nöronu tick'le (N0,N1,N2 sırayla)
//   3) her syn[i] için: pre ateşlediyse akım hesapla, post'un hedef
//      kompartımanına enjekte et
//   4) post nöronu (N3) tick'le
//   5) her syn[i] için: rate counter'ları güncelle, öğrenmeyi uygula
inline NetworkTickResult network_tick(Network& net, int32_t t, fixed_t stimulus) {
    NetworkTickResult result;

    // --- 1) Uyaran enjeksiyonu: N0,N1,N2'nin her iki dalına ---
    if (stimulus > 0) {
        for (int i = 0; i < NET_NUM_PRE; ++i) {
            neuron_inject_current(net.pre[i], net.pre[i].branch_A_id, stimulus, t);
            neuron_inject_current(net.pre[i], net.pre[i].branch_B_id, stimulus, t);
        }
    }

    // --- 2) Presinaptik nöronları tick'le ---
    for (int i = 0; i < NET_NUM_PRE; ++i) {
        result.pre_fired[i] = neuron_tick(net.pre[i], t);
    }

    // --- 3) Sinaptik akım aktarımı: pre ateşlediyse post'a enjekte et ---
    for (int i = 0; i < NET_NUM_SYNAPSES; ++i) {
        int src = net.syn[i].source_neuron_id;
        if (result.pre_fired[src]) {
            fixed_t cur = synapse_transmission_current(net.syn[i]);
            neuron_inject_current(net.post, net.syn[i].target_compartment_id, cur, t);
        }
    }

    // --- 4) Postsinaptik nöronu (N3) tick'le ---
    result.post_fired = neuron_tick(net.post, t);

    // --- 5) Rate counter güncelleme + öğrenme ---
    for (int i = 0; i < NET_NUM_SYNAPSES; ++i) {
        int src = net.syn[i].source_neuron_id;
        rate_counter_update(net.rc_pre[i], result.pre_fired[src]);
        rate_counter_update(net.rc_post[i], result.post_fired);
        synapse_apply_learning(net.syn[i], net.rc_pre[i].count,
                                net.rc_post[i].count, net.eta);
    }

    return result;
}

// N3'ün iki dalının da (Dal A, Dal B) aynı eşzamanlılık penceresi
// içinde dışarıdan girdi alıp almadığını raporlar (neuron_tick'in
// kendi iç coincidence hesabıyla aynı mantık, sadece CSV için dışa açık).
inline bool network_has_coincidence(const Network& net, int32_t t) {
    bool branch_A_input = (net.post.branch_A_last_input_tick >= 0) &&
                          ((t - net.post.branch_A_last_input_tick)
                            <= COINCIDENCE_WINDOW_MS);
    bool branch_B_input = (net.post.branch_B_last_input_tick >= 0) &&
                          ((t - net.post.branch_B_last_input_tick)
                            <= COINCIDENCE_WINDOW_MS);
    return branch_A_input && branch_B_input;
}

#endif // NETWORK_H
