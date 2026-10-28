// bench/ablate/syn_probe.cpp — synapse.h A1 eşdeğerlik sondası.
// Kullanım: derlerken -I ile ya src/ ya da ablate/src/ seçilir; sabit bir
// (r_pre,r_post,eta) dizisi uygulanır, ağırlık+iz dökümü basılır.
// Makrosuz kopya çıktısı orijinalle bit-bit aynı olmalıdır.
#include <cstdint>
#include <cstdio>
#include "synapse.h"

int main() {
    synapse_build_luts();
    Synapse s;
    synapse_init(s, 0, 1, 0);
    fixed_t eta = fixed_from_double(0.2);
    const int seq[][2] = {{1, 1}, {5, 3}, {30, 30}, {0, 5},
                          {12, 0}, {7, 7}, {30, 1}, {2, 29}};
    for (int r = 0; r < 3; ++r)
        for (unsigned k = 0; k < sizeof(seq) / sizeof(seq[0]); ++k) {
            fixed_t dw = synapse_apply_learning(s, seq[k][0], seq[k][1], eta);
            std::printf("%d %d dw=%d w=%d t=%d\n", seq[k][0], seq[k][1],
                        (int)dw, (int)s.weight, (int)s.trace);
        }
    return 0;
}
