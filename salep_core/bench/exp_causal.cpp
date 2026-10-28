// bench/exp_causal.cpp — seyrek-dünya nedensellik S-kolu (AŞAMA 6).
// main_causal_afferent.cpp KABLOSU BİREBİR (sabitler dahil); yalnız sx/sy
// sentetik tren yerine gen.py seyrek-dünya olaylarından okunur.
// Çekirdek DEĞİŞMEZ (include only). Tek faz, öğrenme AÇIK (eta=0.2).
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "../src/sensory_lobe.h"
#include "../src/causality.h"
#include "../src/causal_afferent.h"
#include "../src/predict.h"

namespace {
constexpr int32_t AFF_P1_TAUS[2] = {4, 12};
constexpr int AFF_NUM_P2 = 2;
constexpr fixed_t AFF_SL_AMP = fixed_from_double(1.0);
constexpr fixed_t AFF_P1_AMPS[2] = {fixed_from_double(0.7),
                                    fixed_from_double(4.0)};
constexpr int32_t AFF_TAUS[CAUS_NUM_PRE] = {4, 8, 12, 16};
constexpr int32_t AFF_BW = 2;
constexpr fixed_t AFF_CAUS_ETA = fixed_from_double(0.2);
constexpr fixed_t AFF_PULSE = fixed_from_double(0.8);
constexpr fixed_t AFF_W0_C = fixed_from_double(0.4);
constexpr BurstSpec AFF_SPEC_X = {0, 2, 4};
constexpr BurstSpec AFF_SPEC_Y = {2, 2, 12};
constexpr int32_t AFF_PRED_W = 16;

NeuronParams aff_pre_params(int idx) {
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
    p.tau_isi = AFF_TAUS[idx];
    p.resonance_bw = AFF_BW;
    return p;
}
}  // namespace

int main(int argc, char** argv) {
    const char* ev_path = nullptr;
    const char* out_pre = nullptr;
    int ticks = 30000;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--events") == 0 && i + 1 < argc) ev_path = argv[++i];
        else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) out_pre = argv[++i];
        else if (strcmp(argv[i], "--ticks") == 0 && i + 1 < argc) ticks = atoi(argv[++i]);
        else { std::fprintf(stderr, "bilinmeyen arguman %s\n", argv[i]); return 2; }
    }
    if (!ev_path || !out_pre || ticks <= 0) {
        std::fprintf(stderr, "kullanim: exp_causal --events F --ticks T --out P\n");
        return 2;
    }
    std::vector<char> isX(ticks, 0), isY(ticks, 0), isYL(ticks, 0);
    FILE* ef = fopen(ev_path, "r");
    if (!ef) { std::fprintf(stderr, "HATA: olay acilmadi\n"); return 1; }
    char line[256];
    if (!fgets(line, sizeof(line), ef)) return 1;
    while (fgets(line, sizeof(line), ef)) {
        int tick = atoi(line);
        char* c1 = strchr(line, ',');
        if (!c1 || tick < 0 || tick >= ticks) continue;
        char kind = c1[1];
        char* c2 = strchr(c1 + 1, ',');
        int link = c2 ? atoi(c2 + 1) : -1;
        if (kind == 'X') isX[tick] = 1;
        if (kind == 'Y') {
            isY[tick] = 1;
            if (link >= 0) isYL[tick] = 1;
        }
    }
    fclose(ef);

    synapse_build_luts();
    SensoryLobe lobe;
    SlPostCfg cfg[AFF_NUM_P2] = {{0, 0, 12, fixed_from_double(0.2)},
                                 {1, 0, 12, fixed_from_double(0.2)}};
    sl_init(lobe, AFF_P1_TAUS, 2, cfg, AFF_NUM_P2, AFF_SL_AMP, AFF_P1_AMPS,
            fixed_from_double(0.0));
    CausalityNetwork cn;
    NeuronParams pre_params[CAUS_NUM_PRE];
    for (int i = 0; i < CAUS_NUM_PRE; ++i) pre_params[i] = aff_pre_params(i);
    NeuronParams target_params = {0.04, 0.04, 0.04, 0.005, 0.004, 0.003};
    causality_init(cn, pre_params, target_params, AFF_W0_C, AFF_CAUS_ETA);
    BurstAdapter ad;
    adapter_init(ad, AFF_PULSE);
    Predictor pd;
    predictor_init(pd, AFF_PRED_W);

    std::string tp = std::string(out_pre) + "_tick.csv";
    FILE* tf = fopen(tp.c_str(), "w");
    if (!tf) { std::fprintf(stderr, "HATA: cikti acilmadi\n"); return 1; }
    fprintf(tf, "tick,evx,evy,evyL,pre0,pre2,tgt,coinc,pred\n");
    for (int32_t t = 0; t < ticks; ++t) {
        bool p1p[2] = {(t % 4) == 0, (t % 12) == 0};
        bool sp[P2_MAX] = {false};
        sp[0] = isX[t] != 0;
        sp[1] = isY[t] != 0;
        fixed_t sdw[P2_MAX] = {0};
        SensoryTickResult sr = sensory_tick(lobe, t, p1p, sp, sdw);
        int evx = sr.p2_fired[0] ? 1 : 0;
        int evy = sr.p2_fired[1] ? 1 : 0;
        if (evx) adapter_post_event(ad, t, AFF_SPEC_X);
        if (evy) adapter_post_event(ad, t, AFF_SPEC_Y);
        fixed_t stim[CAUS_NUM_PRE];
        adapter_emit(ad, t, stim);
        fixed_t cdw[CAUS_NUM_SYNAPSES] = {0, 0, 0, 0};
        CausalityTickResult r = causality_tick(cn, t, stim, cdw);
        bool coinc = causality_has_coincidence(cn, t);
        predict_tick(pd, t, r.pre_fired[0], evy != 0);
        fprintf(tf, "%d,%d,%d,%d,%d,%d,%d,%d,%d\n", (int)t, evx, evy,
                isYL[t] ? 1 : 0, r.pre_fired[0] ? 1 : 0,
                r.pre_fired[2] ? 1 : 0, r.target_fired ? 1 : 0,
                coinc ? 1 : 0, predictor_active(pd, t) ? 1 : 0);
    }
    fclose(tf);
    double prec = pd.windows > 0
                      ? (double)pd.predicted_y / (double)pd.windows
                      : 0.0;
    double rec = pd.y_events > 0
                     ? (double)pd.predicted_y / (double)pd.y_events
                     : 0.0;
    std::printf("OZET-CAUSAL win=%ld predy=%ld y=%ld prec=%.4f rec=%.4f "
                "drops=%ld w0=%.4f w2=%.4f\n",
                pd.windows, pd.predicted_y, pd.y_events, prec, rec,
                ad.drops, fixed_to_float(cn.syn[0].weight),
                fixed_to_float(cn.syn[2].weight));
    return 0;
}
