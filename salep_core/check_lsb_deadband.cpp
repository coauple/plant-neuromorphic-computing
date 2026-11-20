// LSB olu-bant denetimi (2026-11-21 00:49, Cumartesi; GOZLEM — kod DONUK).
// Bkz. CLAUDE.md §9.117.
//
// Soru: sabit noktada (Q16.16) carpimsal sonum her degeri dinlenmeye
// indirebiliyor mu? fixed_mul asagi yuvarlar; sonum*sapma < 1 LSB olunca
// sonum 0 olur ve deger "taban"da donar.
// Yontem: depodaki GERCEK compartment_apply_leak / compartment_update_gating
// fonksiyonlari, pattern lobun gercek leak/gdecay degerleriyle 1.0'dan
// baslatilip 200.000 tick girdisiz calistirilir; ayrica -0.2'den (V_RESET)
// alttan yaklasim, K4 iliski matrisi (0.125) ve sinaps erisilebilirlik
// sonumu (AVAIL_LAMBDA 0.005) olculur. Cekirdege dokunulmaz.
//
// Derleme: g++ -std=c++17 -O2 -Isrc check_lsb_deadband.cpp -o check_lsb_deadband
#include <cstdio>
#include "fixed_point.h"
#include "compartment.h"
struct P { const char* name; double leak, gdecay; };
int main() {
    P ps[] = {{"root/soma (P3x3)",0.08,0.005},{"A_K1",0.06,0.004},{"B_K1",0.04,0.003},
              {"A_K2",0.10,0.010},{"B_K2",0.04,0.003},{"A_K3",0.02,0.002},{"B_K3",0.04,0.003},
              {"K4 dallari",0.08,0.005}};
    const double LSB = 1.0/65536;
    printf("%-18s %6s %6s | %-24s | %-24s | %s\n","kompartiman","leak","gdecay",
           "voltaj tabani (1.0'dan)","gating tabani (1.0'dan)","alttan (-0.2'den) voltaj");
    for (auto& p : ps) {
        Compartment c; compartment_init(c);
        c.leak_rate = fixed_from_double(p.leak);
        c.gating_decay_rate = fixed_from_double(p.gdecay);
        c.local_voltage = FIXED_ONE; c.gating_state = FIXED_ONE;
        for (int t = 0; t < 200000; ++t) { compartment_apply_leak(c); compartment_update_gating(c); }
        Compartment d; compartment_init(d);
        d.leak_rate = c.leak_rate; d.gating_decay_rate = c.gating_decay_rate;
        d.local_voltage = fixed_from_double(-0.2);
        for (int t = 0; t < 200000; ++t) compartment_apply_leak(d);
        printf("%-18s %6.3f %6.3f | %4d LSB = %.6f      | %4d LSB = %.6f      | %d LSB\n", p.name, p.leak, p.gdecay,
               c.local_voltage, c.local_voltage*LSB, c.gating_state, c.gating_state*LSB, d.local_voltage);
    }
    // relation matrix and synapse availability decay
    fixed_t r = FIXED_ONE, RL = fixed_from_double(0.125);
    for (int t = 0; t < 200000; ++t) r -= fixed_mul(RL, r);
    printf("K4 iliski matrisi r (leak 0.125): %d LSB = %.6f\n", r, r*LSB);
    fixed_t w = FIXED_ONE, fl = 0, LAM = fixed_from_double(0.005);
    for (int t = 0; t < 200000; ++t) w -= fixed_mul(LAM, w - fl);
    printf("Sinaps agirligi, tabanin ustu (LAMBDA 0.005): taban+%d LSB = +%.6f\n", w - fl, (w-fl)*LSB);
    return 0;
}
