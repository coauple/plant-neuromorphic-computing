#ifndef NEURON_H
#define NEURON_H

#include "compartment.h"

// ---------------------------------------------------------------------------
// Nöron sabitleri
//
// ARCHITECTURE.md §2.2: "sabit boyutlu diziler" kuralı.
// MAX_COMPARTMENTS = MAX_CHILDREN_PER_COMPARTMENT × MAX_BRANCHES × 2 = 12
// Bu adımda 3 kompartıman kullanıyoruz: [0]=kök, [1]=dal_A, [2]=dal_B.
// ---------------------------------------------------------------------------

constexpr int MAX_BRANCHES     = 2;
constexpr int MAX_COMPARTMENTS = MAX_CHILDREN_PER_COMPARTMENT
                                 * MAX_BRANCHES
                                 * 2;  // 12 slot

// Kompartımanlar arası difüzyon katsayısı.
// 0.15 = voltaj farkının %15'i her tick'te akar.
constexpr fixed_t DIFFUSION_COEFF = fixed_from_double(0.15);

// ---------------------------------------------------------------------------
// Eşzamanlılık penceresi (coincidence window)
//
// ARCHITECTURE.md §3: "Soma: iki dalın belirli bir zaman penceresi
// (COINCIDENCE_WINDOW_MS) içinde çakışıp çakışmadığına bakar"
//
// 10 tick = 10 ms pencere. Bir dal "aktif" sayılması için voltajının
// BRANCH_ACTIVE_THRESH'i aşması gerekir; aşma anı "last_active_tick"
// olarak kaydedilir.
//
// Neden 10: çok kısa (3-5 tick) ise hassas senkronizasyon gerekir →
// gerçek sensör sinyallerinde zor. Çok uzun (50+ tick) ise eşzamanlılık
// anlamsızlaşır — her şey "eşzamanlı" sayılır.
// ---------------------------------------------------------------------------

constexpr int32_t COINCIDENCE_WINDOW_MS = 10;

// (BRANCH_ACTIVE_THRESH kaldırıldı — eşzamanlılık artık voltaja değil
// dışarıdan girdi zamanına bakıyor. Bkz. neuron_inject_current.)

// ---------------------------------------------------------------------------
// Eşzamanlılık bonusu
//
// İki dal pencere içinde çakıştığında kök gating'e eklenen bonus.
// Mekanizma: soma_voltage = root_v × (1 + root_gating + COINCIDENCE_BONUS)
//
// NEDEN toplamsal (çarpımsal değil):
//   - Çarpımsal bonus (ör. gating *= 1.5) → gating sıfıra yakınken
//     etkisiz olur, başlangıçta hiç fark yaratmaz.
//   - Toplamsal bonus (ör. gating += 0.8) → gating sıfırken bile
//     soma amplifikasyonunu başlatır. İlk eşzamanlılık olayı bile
//     fark yaratır.
//
// 0.8 = tek başına ateşlemeye yetmez (soma = root_v × 1.8, tipik
// root_v ~0.3 → soma ~0.54 < 1.0), ama gating birikimi ile birlikte
// eşiği aşmaya yardımcı olur.
// ---------------------------------------------------------------------------

constexpr fixed_t COINCIDENCE_BONUS = fixed_from_double(0.8);

// ---------------------------------------------------------------------------
// DendriticNeuron yapısı — dallanma (branching) versiyonu
//
// ARCHITECTURE.md §2.4 + §3'ten türetildi.
//
// Topoloji:
//   [0] kök (root) ← somaya bağlı, parent_id=-1
//    ├─ [1] Dal A (branch_phase)  ← faz/rezonans dalı
//    └─ [2] Dal B (branch_sensor) ← sensör-spike dalı
//
// Her dal yaprak düğüm (kendi çocuğu yok).
// Soma voltajı artık sadece kök voltajına değil, iki dalın
// eşzamanlılık durumuna da bağlı.
//
// branch_A_id, branch_B_id: ARCHITECTURE.md terminolojisiyle
// indeksleri isme bağlıyoruz. Generic N-dal'a geçişte bunlar
// bir dizi olacak.
// ---------------------------------------------------------------------------

struct DendriticNeuron {
    int     neuron_id;
    fixed_t threshold;
    fixed_t soma_voltage;
    int32_t last_fire_time_ms;

    Compartment compartments[MAX_COMPARTMENTS];
    int num_compartments;
    int root_compartment_id;

    // --- Dallanma bilgisi ---
    int branch_A_id;              // Dal A (faz/rezonans) kompartıman indeksi
    int branch_B_id;              // Dal B (sensör-spike) kompartıman indeksi

    // Her dalın son DIŞARIDAN GİRDİ ALMA anı.
    // -1 = henüz hiç girdi almadı.
    //
    // ÖNCEKİ HATA: voltaja (local_voltage > eşik) bakılıyordu.
    // Sorun: Dal A'ya enjekte edilen akım difüzyonla A→Kök→B yolunu
    // izliyor ve Dal B'nin voltajını eşiğin üstüne çıkarıyordu.
    // Sonuç: tek dal uyarılırken bile sahte "eşzamanlılık" algılanıyordu.
    //
    // DÜZELTME: Eşzamanlılık, dalın voltajına değil dışarıdan
    // (enjeksiyon / ileride sinaps) girdi alıp almadığına bakar.
    // neuron_inject_current içinde hedef dal'ın last_input_tick'i
    // güncellenir.
    int32_t branch_A_last_input_tick;
    int32_t branch_B_last_input_tick;

    // --- ISI-tau rezonans kapısı (yalnız Dal A) ---
    // Anayasa §2.3/§3: tau_resonance bugüne dek ölü alandı (synapse.h).
    // Rezonans burada, Dal A giriş kapısı olarak yaşar; Synapse.tau
    // bu adımda hâlâ kullanılmıyor (bilinçli: tek filtre noktası).
    // tau_isi/resonance_bw: tick tamsayısı; ikisi de 0 = kapı kapalı.
    // last_wire_tick_A: tel üzerindeki son darbe (sönümlenmiş olsa bile
    // ISI hafızası için güncellenir). branch_A_last_input_tick ise yalnız
    // kapıdan GEÇEN (mu>0) darbelerde güncellenir → sönümlenen bant
    // sahte coincidence üretmez.
    int32_t tau_isi;
    int32_t resonance_bw;
    int32_t last_wire_tick_A;

    // --- PLIR (Phase-Locked Interval Resonator, opt-in; §9.8) ---
    // plir_mode=0 (varsayilan): eski ISI kapisi yolu birebir (regresyon).
    // plir_mode=1: ISI hafizasi yalniz KABUL edilen darbede guncellenir
    //   (last_resonant_tick_A); yabanci darbe reddedilir (ref korunur,
    //   voltaj yok). Taze kabul: ilk darbe (ref<0) veya
    //   isi > plir_lock_lost (kilit dustu, yeniden kilitlen).
    // plir_lock_lost<=0 ise 2*tau_isi+resonance_bw kullanilir (MC degeri).
    int32_t plir_mode;
    int32_t last_resonant_tick_A;
    int32_t plir_lock_lost;

    // --- B-dali PLIR kapisi (opt-in; Duyusal Lob v2, §9.14) ---
    // A-PLIR ile birebir ayni kural, Dal B (sensor faz hatti) icin:
    // ISI hafizasi yalniz KABUL edilen darbede guncellenir
    // (last_resonant_tick_B); yabanci periyot reddedilir (ref korunur,
    // voltaj + coincidence yok) -> sahte eszamanlilik uretmez.
    // Tum alanlar 0 = kapisiz -> genel yol aynen (regresyon).
    int32_t plir_mode_B;
    int32_t tau_isi_B;
    int32_t resonance_bw_B;
    int32_t last_resonant_tick_B;
    int32_t plir_lock_lost_B;
};

// ---------------------------------------------------------------------------
// Nöron başlatma — 3 kompartımanlı dallanma yapısı
//
// Topoloji:
//   [0] kök  (somaya bağlı, parent=-1, çocukları: 1, 2)
//   [1] Dal A (branch_phase)  — köke bağlı (parent=0)
//   [2] Dal B (branch_sensor) — köke bağlı (parent=0)
//
// Parametre seçimleri ve gerekçeleri:
//
//   Kök (idx=0):
//     leak_rate=0.08 — hızlı sızıntı, toplama noktası olarak çalışır
//     gating_decay=0.005 — yavaş gating sönümü (yarılanma ~139 tick)
//     Gerekçe: kök, dallardan gelen sinyali toplayıp soma'ya ileten
//     entegratör. Hızlı leak = sadece güçlü/sürekli girdiler hayatta
//     kalır. Yavaş gating = hafıza uzun yaşar.
//
//   Dal A (idx=1, branch_phase):
//     leak_rate=0.06 — orta sızıntı
//     gating_decay=0.004 — orta-yavaş gating (yarılanma ~173 tick)
//     Gerekçe: faz/rezonans sinyali sürekli bir salınım → orta sızıntı
//     sürekli girdinin birikmesine izin verir. Gating biraz daha hızlı
//     sönümlenir çünkü faz bilgisi zamanla eskir.
//
//   Dal B (idx=2, branch_sensor):
//     leak_rate=0.04 — yavaş sızıntı (yüksek membran direnci)
//     gating_decay=0.003 — en yavaş gating (yarılanma ~231 tick)
//     Gerekçe: sensör spike'ları keskin ve seyrek → yavaş sızıntı
//     tek bir spike'ın etkisini uzun tutar. En yavaş gating = sensör
//     hafızası en uzun yaşar (bitki sinyalleri yavaş değişir).
// ---------------------------------------------------------------------------

inline void neuron_init(DendriticNeuron& n, int id) {
    n.neuron_id           = id;
    n.threshold           = V_THRESHOLD;
    n.soma_voltage        = V_REST;
    n.last_fire_time_ms   = -1;
    n.num_compartments    = 3;
    n.root_compartment_id = 0;
    n.branch_A_id         = 1;
    n.branch_B_id         = 2;
    n.branch_A_last_input_tick = -1;
    n.branch_B_last_input_tick = -1;
    n.tau_isi = 0;
    n.resonance_bw = 0;
    n.last_wire_tick_A = -1;
    n.plir_mode = 0;
    n.last_resonant_tick_A = -1;
    n.plir_lock_lost = 0;
    n.plir_mode_B = 0;
    n.tau_isi_B = 0;
    n.resonance_bw_B = 0;
    n.last_resonant_tick_B = -1;
    n.plir_lock_lost_B = 0;

    // --- Kök kompartıman (indeks 0) — somaya bağlı ---
    compartment_init(n.compartments[0]);
    n.compartments[0].leak_rate         = fixed_from_double(0.08);
    n.compartments[0].gating_decay_rate = fixed_from_double(0.005);
    n.compartments[0].parent_id         = -1;
    n.compartments[0].child_ids[0]      = 1;  // Dal A
    n.compartments[0].child_ids[1]      = 2;  // Dal B
    n.compartments[0].num_children      = 2;

    // --- Dal A: branch_phase (indeks 1) — faz/rezonans dalı ---
    compartment_init(n.compartments[1]);
    n.compartments[1].leak_rate         = fixed_from_double(0.06);
    n.compartments[1].gating_decay_rate = fixed_from_double(0.004);
    n.compartments[1].parent_id         = 0;
    // yaprak düğüm — çocuğu yok

    // --- Dal B: branch_sensor (indeks 2) — sensör-spike dalı ---
    compartment_init(n.compartments[2]);
    n.compartments[2].leak_rate         = fixed_from_double(0.04);
    n.compartments[2].gating_decay_rate = fixed_from_double(0.003);
    n.compartments[2].parent_id         = 0;
    // yaprak düğüm — çocuğu yok
}

// ---------------------------------------------------------------------------
// Parametrik nöron başlatma — çoklu nöron tipi desteği
//
// SKILL.md §3: "Her nöronun tau_resonance değerine göre ayarlı dalları var."
// SKILL.md §6: "2-3 farklı nöron tipi oluştur, aynı uyaranla test et."
//
// Bu fonksiyon, neuron_init ile aynı topolojiyi kurar (kök + 2 dal)
// ama leak_rate ve gating_decay_rate değerlerini dışarıdan alır.
//
// Parametreler (double, içeride fixed'e çevrilir):
//   root_leak, brA_leak, brB_leak       — sızıntı oranları
//   root_gdecay, brA_gdecay, brB_gdecay — gating sönüm oranları
//
// Topoloji değişmez: [0]=kök, [1]=Dal A (faz), [2]=Dal B (sensör).
// ---------------------------------------------------------------------------

struct NeuronParams {
    double root_leak;     double brA_leak;     double brB_leak;
    double root_gdecay;   double brA_gdecay;   double brB_gdecay;
    // ISI-tau rezonans kapısı (Dal A). Tick tamsayısı; 0 = kapı kapalı
    // (eski davranış birebir korunur). Sona eklendi: mevcut 6-alanlı
    // aggregate init'ler bozulmaz (eksik alanlar sıfırlanır).
    int32_t tau_isi = 0;
    int32_t resonance_bw = 0;
    // PLIR opt-in (§9.8). Sona eklendi: mevcut init'ler bozulmaz.
    int32_t plir_mode = 0;
    int32_t plir_lock_lost = 0;
    // B-dali PLIR opt-in (§9.14). Sona eklendi: mevcut init'ler bozulmaz.
    int32_t plir_mode_B = 0;
    int32_t tau_isi_B = 0;
    int32_t resonance_bw_B = 0;
    int32_t plir_lock_lost_B = 0;
};

inline void neuron_init_with_params(DendriticNeuron& n, int id,
                                     const NeuronParams& p) {
    n.neuron_id           = id;
    n.threshold           = V_THRESHOLD;
    n.soma_voltage        = V_REST;
    n.last_fire_time_ms   = -1;
    n.num_compartments    = 3;
    n.root_compartment_id = 0;
    n.branch_A_id         = 1;
    n.branch_B_id         = 2;
    n.branch_A_last_input_tick = -1;
    n.branch_B_last_input_tick = -1;
    n.tau_isi = p.tau_isi;
    n.resonance_bw = p.resonance_bw;
    n.last_wire_tick_A = -1;
    n.plir_mode = p.plir_mode;
    n.last_resonant_tick_A = -1;
    n.plir_lock_lost = p.plir_lock_lost;
    n.plir_mode_B = p.plir_mode_B;
    n.tau_isi_B = p.tau_isi_B;
    n.resonance_bw_B = p.resonance_bw_B;
    n.last_resonant_tick_B = -1;
    n.plir_lock_lost_B = p.plir_lock_lost_B;

    // --- Kök kompartıman (indeks 0) ---
    compartment_init(n.compartments[0]);
    n.compartments[0].leak_rate         = fixed_from_double(p.root_leak);
    n.compartments[0].gating_decay_rate = fixed_from_double(p.root_gdecay);
    n.compartments[0].parent_id         = -1;
    n.compartments[0].child_ids[0]      = 1;
    n.compartments[0].child_ids[1]      = 2;
    n.compartments[0].num_children      = 2;

    // --- Dal A (branch_phase, indeks 1) ---
    compartment_init(n.compartments[1]);
    n.compartments[1].leak_rate         = fixed_from_double(p.brA_leak);
    n.compartments[1].gating_decay_rate = fixed_from_double(p.brA_gdecay);
    n.compartments[1].parent_id         = 0;

    // --- Dal B (branch_sensor, indeks 2) ---
    compartment_init(n.compartments[2]);
    n.compartments[2].leak_rate         = fixed_from_double(p.brB_leak);
    n.compartments[2].gating_decay_rate = fixed_from_double(p.brB_gdecay);
    n.compartments[2].parent_id         = 0;
}

// ---------------------------------------------------------------------------
// Akım enjeksiyonu — GİRDİ ZAMANI TAKİBİ EKLENDİ
//
// Hedef kompartıman bir dal ise (branch_A veya branch_B), o dalın
// last_input_tick'ini günceller. Eşzamanlılık kararı bu zamana bakar.
//
// current_time_ms: dışarıdan geçirilir (neuron_tick ile aynı saat).
// ---------------------------------------------------------------------------

inline void neuron_inject_current(DendriticNeuron& n,
                                   int compartment_id,
                                   fixed_t current,
                                   int32_t current_time_ms) {
    // PLIR yolu (opt-in, §9.8): ISI hafizasi yalniz KABUL edilen
    // darbede guncellenir. Tamsayi tick + tek fixed_div → HLS uyumlu.
    // validate_fdm.py ile kalibre (FDM_BW=1, LOCK=2*tau+bw).
    if (compartment_id == n.branch_A_id && n.plir_mode != 0) {
        // Gecersiz kapi parametresi: kapisiz kabul (mu=1), ref yine isler.
        if (n.tau_isi <= 0 || n.resonance_bw <= 0) {
            n.last_resonant_tick_A = current_time_ms;
            n.compartments[compartment_id].local_voltage += current;
            n.branch_A_last_input_tick = current_time_ms;
            return;
        }
        int32_t lock =
            (n.plir_lock_lost > 0)
                ? n.plir_lock_lost
                : (2 * n.tau_isi + n.resonance_bw);
        // Taze kabul: ilk darbe veya kilit dustu (yeniden kilitlen).
        if (n.last_resonant_tick_A < 0 ||
            (current_time_ms - n.last_resonant_tick_A) > lock) {
            n.last_resonant_tick_A = current_time_ms;
            n.compartments[compartment_id].local_voltage += current;
            n.branch_A_last_input_tick = current_time_ms;
            return;
        }
        int32_t isi = current_time_ms - n.last_resonant_tick_A;
        int32_t diff = isi - n.tau_isi;
        if (diff < 0) diff = -diff;
        if (diff >= n.resonance_bw) {
            return;  // REDDET: ref korunur, voltaj + coincidence yok
        }
        fixed_t mu = fixed_div(fixed_from_int(n.resonance_bw - diff),
                               fixed_from_int(n.resonance_bw));
        n.last_resonant_tick_A = current_time_ms;
        if (mu <= 0) return;
        current = fixed_mul(current, mu);
        n.compartments[compartment_id].local_voltage += current;
        n.branch_A_last_input_tick = current_time_ms;
        return;
    }

    // B-dali PLIR kapisi (opt-in, §9.14): A-PLIR blogu ile birebir ayni
    // kural, Dal B (sensor faz hatti) icin. plir_mode_B=0 iken bu blok
    // hic calismaz -> genel yol aynen (regresyon).
    if (compartment_id == n.branch_B_id && n.plir_mode_B != 0) {
        // Gecersiz kapi parametresi: kapisiz kabul (mu=1), ref yine isler.
        if (n.tau_isi_B <= 0 || n.resonance_bw_B <= 0) {
            n.last_resonant_tick_B = current_time_ms;
            n.compartments[compartment_id].local_voltage += current;
            n.branch_B_last_input_tick = current_time_ms;
            return;
        }
        int32_t block =
            (n.plir_lock_lost_B > 0)
                ? n.plir_lock_lost_B
                : (2 * n.tau_isi_B + n.resonance_bw_B);
        // Taze kabul: ilk darbe veya kilit dustu (yeniden kilitlen).
        if (n.last_resonant_tick_B < 0 ||
            (current_time_ms - n.last_resonant_tick_B) > block) {
            n.last_resonant_tick_B = current_time_ms;
            n.compartments[compartment_id].local_voltage += current;
            n.branch_B_last_input_tick = current_time_ms;
            return;
        }
        int32_t bisi = current_time_ms - n.last_resonant_tick_B;
        int32_t bdiff = bisi - n.tau_isi_B;
        if (bdiff < 0) bdiff = -bdiff;
        if (bdiff >= n.resonance_bw_B) {
            return;  // REDDET: ref korunur, voltaj + coincidence yok
        }
        fixed_t bmu = fixed_div(fixed_from_int(n.resonance_bw_B - bdiff),
                                fixed_from_int(n.resonance_bw_B));
        n.last_resonant_tick_B = current_time_ms;
        if (bmu <= 0) return;
        current = fixed_mul(current, bmu);
        n.compartments[compartment_id].local_voltage += current;
        n.branch_B_last_input_tick = current_time_ms;
        return;
    }

    // ISI-tau rezonans kapısı (yalnız Dal A, kapı açıkken):
    //   mu = clamp(1 - |ISI - tau| / bw, 0, 1); current *= mu.
    // Kapı kapalı (tau<=0 veya bw<=0) veya ilk darbe (tel hafızası -1)
    // ise mu=1 → eski davranış birebir aynı (regresyon güvenli).
    // Tamsayı tick + tek fixed_div (darbesel, tick başına değil) → HLS uyumlu.
    // NOT: plir_mode=0 iken bu blok tarihsel haliyle korunur — dokunma.
    if (compartment_id == n.branch_A_id && n.tau_isi > 0 && n.resonance_bw > 0) {
        fixed_t mu = FIXED_ONE;
        if (n.last_wire_tick_A >= 0) {
            int32_t isi = current_time_ms - n.last_wire_tick_A;
            int32_t diff = isi - n.tau_isi;
            if (diff < 0) diff = -diff;
            if (diff >= n.resonance_bw) {
                mu = 0;
            } else {
                mu = fixed_div(fixed_from_int(n.resonance_bw - diff),
                               fixed_from_int(n.resonance_bw));
            }
        }
        n.last_wire_tick_A = current_time_ms;
        if (mu <= 0) return;  // sönümlenen bant: voltaj + coincidence yok
        current = fixed_mul(current, mu);
        n.compartments[compartment_id].local_voltage += current;
        n.branch_A_last_input_tick = current_time_ms;
        return;
    }

    n.compartments[compartment_id].local_voltage += current;

    // Hedef dal ise, o dalın son girdi zamanını kaydet
    if (compartment_id == n.branch_A_id) {
        n.branch_A_last_input_tick = current_time_ms;
        n.last_wire_tick_A = current_time_ms;
    }
    if (compartment_id == n.branch_B_id) {
        n.branch_B_last_input_tick = current_time_ms;
    }
}

// ---------------------------------------------------------------------------
// Tek tick simülasyonu — dallanma + eşzamanlılık algılama versiyonu
//
// Sıra:
//   1. Difüzyon (snapshot-then-apply, 3 kompartıman arası)
//   2. Sızıntı  (her kompartımanda bağımsız)
//   3. Gating   (her kompartımanda bağımsız)
//   4. Dal aktivite takibi (last_active_tick güncelleme)
//   5. Soma voltajı + eşzamanlılık bonusu + ateşleme kararı
//
// Soma hesaplama — YENI:
//
//   coincidence = (|tick − A_last_active| ≤ WINDOW) AND
//                 (|tick − B_last_active| ≤ WINDOW)
//
//   if (coincidence)
//       effective_gating = root_gating + COINCIDENCE_BONUS
//   else
//       effective_gating = root_gating
//
//   soma_voltage = root_voltage × (1 + effective_gating)
//
// Etkisi:
//   - Tek dal aktif: soma = root_v × (1 + root_gating)  [eski davranış]
//   - İki dal aktif: soma = root_v × (1 + root_gating + 0.8)
//     → aynı root_v'de %80 daha yüksek amplifikasyon
//     → eşiğe çok daha kolay ulaşılır
//
// Ateşleme: soma > threshold → spike, global reset.
// ---------------------------------------------------------------------------

inline bool neuron_tick(DendriticNeuron& n, int32_t current_time_ms) {
    // --- 1. Difüzyon: snapshot-then-apply ---
    fixed_t snap[MAX_COMPARTMENTS];
    for (int i = 0; i < n.num_compartments; ++i) {
        snap[i] = n.compartments[i].local_voltage;
    }

    for (int i = 0; i < n.num_compartments; ++i) {
        Compartment& c = n.compartments[i];
        // Ebeveyne doğru difüzyon
        if (c.parent_id >= 0) {
            compartment_apply_diffusion(c, snap[c.parent_id], DIFFUSION_COEFF);
        }
        // Çocuklara doğru difüzyon
        for (int j = 0; j < c.num_children; ++j) {
            int child_id = c.child_ids[j];
            if (child_id >= 0) {
                compartment_apply_diffusion(c, snap[child_id], DIFFUSION_COEFF);
            }
        }
    }

    // --- 2. Sızıntı ---
    for (int i = 0; i < n.num_compartments; ++i) {
        compartment_apply_leak(n.compartments[i]);
    }

    // --- 3. Gating state güncelleme ---
    for (int i = 0; i < n.num_compartments; ++i) {
        compartment_update_gating(n.compartments[i]);
    }

    // --- 4. Soma voltajı + eşzamanlılık kararı ---
    //
    // Eşzamanlılık, dalların VOLTAJINA değil DIŞARIDAN GİRDİ ALIP
    // ALMADIĞINA bakar. last_input_tick, neuron_inject_current
    // içinde güncellenir — difüzyonla gelen voltaj yanlışlıkla
    // eşzamanlılık tetiklemez.
    Compartment& root = n.compartments[n.root_compartment_id];

    // Eşzamanlılık kontrolü: her iki dal da pencere içinde girdi aldı mı?
    bool branch_A_input = (n.branch_A_last_input_tick >= 0) &&
                           ((current_time_ms - n.branch_A_last_input_tick)
                             <= COINCIDENCE_WINDOW_MS);
    bool branch_B_input = (n.branch_B_last_input_tick >= 0) &&
                           ((current_time_ms - n.branch_B_last_input_tick)
                             <= COINCIDENCE_WINDOW_MS);
    bool coincidence = branch_A_input && branch_B_input;

    // Efektif gating: eşzamanlılık varsa bonus ekle
    fixed_t effective_gating = root.gating_state;
    if (coincidence) {
        effective_gating += COINCIDENCE_BONUS;
    }

    // soma = root_voltage × (1 + effective_gating)
    n.soma_voltage = fixed_mul(root.local_voltage,
                                FIXED_ONE + effective_gating);

    // --- 6. Ateşleme kararı ---
    bool fired = false;
    if (n.soma_voltage > n.threshold) {
        fired = true;
        n.last_fire_time_ms = current_time_ms;

        // Global reset: tüm kompartımanları sıfırla
        for (int i = 0; i < n.num_compartments; ++i) {
            n.compartments[i].local_voltage = V_RESET;
        }
        n.soma_voltage = V_RESET;
        // Gating sıfırlanmaz — ateşleme gating hafızasını silmez.
        // Aktivite tick'leri de sıfırlanmaz — pencere doğal olarak kapanır.
    }

    return fired;
}

#endif // NEURON_H
