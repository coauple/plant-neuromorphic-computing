#ifndef PREDICT_H
#define PREDICT_H

#include <cstdint>

// ---------------------------------------------------------------------------
// Tek-adim ongoru — ogrenilmis kosullulugun okunmasi (ARCHITECTURE.md §5.1)
//
// Mekanizma: neden-kanal atesi tahmin penceresi acar (W tick); pencere
// icinde gelen etki olayi isabet sayilir. Pencere disinda gelen etki
// iska; etki gelmeden kapanan pencere bos-yanlis alarmdir (dunya sessiz
// kaldi — mekanizma dogru, dunya uymadi; gozlem olarak raporlanir).
// Girdi lob-icidir (pre atesi); skorlama dunya-gercegine (Y olaylari)
// karsidir. Kesinlik (precision) kontrolu yogun-periyodik dunyada
// anlamsizdir (Y her yerde) — seyrek-dunya takip isidir.
// ---------------------------------------------------------------------------

struct Predictor {
    int32_t window;        // tahmin penceresi (tick, MC: 16)
    int32_t active_until;  // pencere bitisi (t <= active_until ise aktif)
    int32_t last_cause;    // son neden atesi (lead olcumu)
    long cause_fires;      // neden atesi sayisi
    long windows;          // acilan (birlesik-sayimli) pencere
    long y_events;         // etki olayi sayisi
    long predicted_y;      // pencerede yakalanan etki
    long lead_sum;         // yakalama lead toplami (etki - neden atesi)
    long lead_n;
};

inline void predictor_init(Predictor& p, int32_t window) {
    p.window = window;
    p.active_until = -1000000;
    p.last_cause = -1000000;
    p.cause_fires = 0;
    p.windows = 0;
    p.y_events = 0;
    p.predicted_y = 0;
    p.lead_sum = 0;
    p.lead_n = 0;
}

// Tek tick: neden atesi (pre0) + etki olayi (Y) islenir.
inline void predict_tick(Predictor& p, int32_t t, bool cause_fired,
                         bool y_event) {
    if (cause_fired) {
        p.cause_fires++;
        if (t > p.active_until) p.windows++;
        p.active_until = t + p.window;
        p.last_cause = t;
    }
    if (y_event) {
        p.y_events++;
        if (t <= p.active_until) {
            p.predicted_y++;
            p.lead_sum += (t - p.last_cause);
            p.lead_n++;
        }
    }
}

inline bool predictor_active(const Predictor& p, int32_t t) {
    return t <= p.active_until;
}

#endif  // PREDICT_H
