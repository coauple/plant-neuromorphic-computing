// bench/cost_probe.cpp — sizeof + durum min/max ölçümü (AŞAMA 8).
// Çekirdeği include eder (salt-okuma); FDM'yi gerçek tel girdisiyle koşturup
// her durum değişkeninin gözlenen min/max'ını yazar.
// Kullanım: cost_probe <wire_csv> <tau0,tau1,...>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "../src/fdm.h"
#include "../src/synapse.h"
#include "../src/sensory_lobe.h"
#include "../src/causality.h"
#include "../src/predict.h"
#include "../src/causal_afferent.h"

int main(int argc, char** argv) {
    std::printf("sizeof fixed_t=%d\n", (int)sizeof(fixed_t));
    std::printf("sizeof Compartment=%d\n", (int)sizeof(Compartment));
    std::printf("sizeof DendriticNeuron=%d\n", (int)sizeof(DendriticNeuron));
    std::printf("sizeof Synapse=%d\n", (int)sizeof(Synapse));
    std::printf("sizeof FdmNetwork=%d\n", (int)sizeof(FdmNetwork));
    std::printf("sizeof SensoryLobe=%d\n", (int)sizeof(SensoryLobe));
    std::printf("sizeof CausalityNetwork=%d\n", (int)sizeof(CausalityNetwork));
    std::printf("sizeof Predictor=%d\n", (int)sizeof(Predictor));
    std::printf("sizeof BurstAdapter=%d\n", (int)sizeof(BurstAdapter));
    std::printf("LUT G=%d Q=%d S=%d bayt\n",
                (int)sizeof(G_LUT), (int)sizeof(Q_LUT), (int)sizeof(S_LUT));
    if (argc < 3) return 0;
    // Tel yükle.
    FILE* f = fopen(argv[1], "r");
    if (!f) return 1;
    std::vector<int32_t> wire;
    char line[256];
    if (!fgets(line, sizeof(line), f)) return 1;
    while (fgets(line, sizeof(line), f)) {
        char* c = strchr(line, ',');
        if (c) wire.push_back((int32_t)strtol(c + 1, nullptr, 10));
    }
    fclose(f);
    std::vector<int> taus;
    for (const char* p = argv[2]; *p;) {
        taus.push_back(atoi(p));
        while (*p && *p != ',') ++p;
        if (*p == ',') ++p;
    }
    FdmNetwork net;
    int32_t ta[3] = {0, 0, 0};
    int po[3] = {8, 8, 8};
    for (size_t b = 0; b < taus.size() && b < 3; ++b) ta[b] = taus[b];
    fdm_init(net, ta, po, (int)taus.size(), 1, 7001);
    double mnV = 1e9, mxV = -1e9, mnG = 1e9, mxG = -1e9, mnS = 1e9,
           mxS = -1e9;
    for (size_t t = 0; t < wire.size(); ++t) {
        fdm_tick(net, (int32_t)t, wire[t]);
        for (size_t b = 0; b < taus.size(); ++b)
            for (int m = 0; m < po[b]; ++m) {
                DendriticNeuron& n = net.band[b][m];
                for (int c = 0; c < MAX_COMPARTMENTS; ++c) {
                    double v = fixed_to_float(n.compartments[c].local_voltage);
                    double g = fixed_to_float(n.compartments[c].gating_state);
                    if (v < mnV) mnV = v;
                    if (v > mxV) mxV = v;
                    if (g < mnG) mnG = g;
                    if (g > mxG) mxG = g;
                }
                double s = fixed_to_float(n.soma_voltage);
                if (s < mnS) mnS = s;
                if (s > mxS) mxS = s;
            }
    }
    std::printf("minmax V=[%.4f,%.4f] gating=[%.4f,%.4f] soma=[%.4f,%.4f] "
                "ntick=%d\n",
                mnV, mxV, mnG, mxG, mnS, mxS, (int)wire.size());
    return 0;
}
