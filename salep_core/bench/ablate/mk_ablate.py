#!/usr/bin/env python3
"""bench/ablate/mk_ablate.py — çekirdek KOPYASI + #ifdef yamaları (AŞAMA 4).

Orijinal src/*.h'ye DOKUNMAZ. bench/ablate/src/'a kopyalar, iki korumalı
yama uygular (anchor assert'li):
  ABL_NO_BONUS (neuron.h): coincidence bonusu atlanır.
  ABL_NO_TRACE (synapse.h): REV-LEARN iz/gevşeme atlanır (saf dw).
Makrosuz derlenen kopya, orijinalle bit-bit aynı davranmalıdır (A1 kapısı
stage4.sh'de kanıtlanır).
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")
DST = os.path.join(ROOT, "bench", "ablate", "src")

BONUS_OLD = """    fixed_t effective_gating = root.gating_state;
    if (coincidence) {
        effective_gating += COINCIDENCE_BONUS;
    }"""
BONUS_NEW = """    fixed_t effective_gating = root.gating_state;
#ifndef ABL_NO_BONUS
    if (coincidence) {
        effective_gating += COINCIDENCE_BONUS;
    }
#endif"""

TRACE_OLD = """inline fixed_t synapse_apply_learning(Synapse& syn, int r_pre, int r_post, fixed_t eta) {
    fixed_t dw = synapse_compute_dw(r_pre, r_post, syn.weight, eta);
    if (dw > 0) {"""
TRACE_NEW = """inline fixed_t synapse_apply_learning(Synapse& syn, int r_pre, int r_post, fixed_t eta) {
    fixed_t dw = synapse_compute_dw(r_pre, r_post, syn.weight, eta);
#ifdef ABL_NO_TRACE
    syn.weight += dw;
    if (syn.weight < 0)     syn.weight = 0;
    if (syn.weight > W_MAX) syn.weight = W_MAX;
    return dw;
#else
    if (dw > 0) {"""
TRACE_END_OLD = """    if (syn.weight < 0)     syn.weight = 0;
    if (syn.weight > W_MAX) syn.weight = W_MAX;
    return dw;
}

#endif // SYNAPSE_H"""
TRACE_END_NEW = """    if (syn.weight < 0)     syn.weight = 0;
    if (syn.weight > W_MAX) syn.weight = W_MAX;
    return dw;
#endif
}

#endif // SYNAPSE_H"""

MUL_OLD = """inline fixed_t fixed_mul(fixed_t a, fixed_t b) {
    return static_cast<fixed_t>((static_cast<int64_t>(a) * b) >> FIXED_SHIFT);
}"""
MUL_NEW = """#ifdef COUNT_OPS
static long bench_cnt_mul = 0;
static long bench_cnt_div = 0;
#endif
inline fixed_t fixed_mul(fixed_t a, fixed_t b) {
#ifdef COUNT_OPS
    bench_cnt_mul++;
#endif
    return static_cast<fixed_t>((static_cast<int64_t>(a) * b) >> FIXED_SHIFT);
}"""
DIV_OLD = """inline fixed_t fixed_div(fixed_t a, fixed_t b) {
    return static_cast<fixed_t>((static_cast<int64_t>(a) << FIXED_SHIFT) / b);
}"""
DIV_NEW = """inline fixed_t fixed_div(fixed_t a, fixed_t b) {
#ifdef COUNT_OPS
    bench_cnt_div++;
#endif
    return static_cast<fixed_t>((static_cast<int64_t>(a) << FIXED_SHIFT) / b);
}"""


def main():
    if os.path.exists(DST):
        shutil.rmtree(DST)
    os.makedirs(DST)
    for fn in os.listdir(SRC):
        if fn.endswith(".h"):
            shutil.copy(os.path.join(SRC, fn), os.path.join(DST, fn))
    p = os.path.join(DST, "neuron.h")
    s = open(p).read()
    assert s.count(BONUS_OLD) == 1, "bonus anchor bulunamadi"
    open(p, "w").write(s.replace(BONUS_OLD, BONUS_NEW))
    p = os.path.join(DST, "synapse.h")
    s = open(p).read()
    assert s.count(TRACE_OLD) == 1, "trace anchor bulunamadi"
    assert s.count(TRACE_END_OLD) == 1, "trace-end anchor bulunamadi"
    s = s.replace(TRACE_OLD, TRACE_NEW).replace(TRACE_END_OLD, TRACE_END_NEW)
    open(p, "w").write(s)
    p = os.path.join(DST, "fixed_point.h")
    s = open(p).read()
    assert s.count(MUL_OLD) == 1, "mul anchor bulunamadi"
    assert s.count(DIV_OLD) == 1, "div anchor bulunamadi"
    s = s.replace(MUL_OLD, MUL_NEW).replace(DIV_OLD, DIV_NEW)
    open(p, "w").write(s)
    print("OK mk_ablate: kopya + 3 ifdef yamasi (bonus/trace/count)")


if __name__ == "__main__":
    sys.exit(main())
