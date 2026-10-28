// ---------------------------------------------------------------------------
// Pattern Lobe persistence katmani (§9.113) — AYRI KATMAN, cekirdek disi.
//
// Kapsam: yalniz ogrenilmis state (w/T/r). Ogrenme kurali, K4 mekanizmasi,
// REV-LEARN, sabitler, tick dongusu DEGISTIRILMEZ. Bu dosya harness
// tarafindan cagrilir (main_pattern_lobe.cpp); cekirdek *.h'lari include
// eder ama onlara yazmaz (salt state tasiyici).
//
// Format (sabit layout, little-endian, fixed-width; JSON/pickle/double yok):
//   header (32 B): magic u32 "PLST", version u32 (=1), p3n u32 (=29),
//     nsyn u32 (=18), nb u32 (=58), last_tick u32 (bilgi; zaman episodic),
//     flags u32 (=0), reserved u32 (=0)
//   w[522] i32 LE (birim-major, sinaps-minor; W-cikti sirasiyla ayni)
//   T[522] i32 LE (ayni sira)
//   r[58][58] i32 LE (satir-major, tum matris; simetri load'da dogrulanmaz,
//     oldugu gibi tasinir)
//   crc32 u32 LE (header+payload uzerinden; poly 0xEDB88320)
// Toplam: 32 + 2088 + 2088 + 13456 + 4 = 17668 B.
//
// Kurallar: load tum dogrulamalar (magic/version/boyut/dims/CRC) gecmeden
// state'e DOKUNMAZ (kismi yukleme yok); bozuk dosyada cagiran temiz baslar.
// ---------------------------------------------------------------------------

#ifndef PATTERN_STATE_H
#define PATTERN_STATE_H

#include <cstdint>
#include <cstdio>
#include <vector>
#include "pattern_lobe.h"  // V4cUnit/V4cK4Net/p3x3_syn (salt-okunur erisim)

namespace plstate {

constexpr uint32_t MAGIC = 0x54534C50u;  // "PLST" LE
constexpr uint32_t VERSION = 1u;
constexpr uint32_t HEADER_LEN = 32u;
constexpr size_t W_COUNT = (size_t)P3X3_N * (size_t)P3X3_NSYN;  // 522
constexpr size_t R_COUNT = (size_t)V4C_NB * (size_t)V4C_NB;     // 3364
constexpr size_t PAYLOAD_LEN =
    W_COUNT * 4u + W_COUNT * 4u + R_COUNT * 4u;  // 17632
constexpr size_t TOTAL_LEN = HEADER_LEN + PAYLOAD_LEN + 4u;  // 17668

enum LoadResult {
    LOAD_OK = 0,
    LOAD_ERR_OPEN = 1,
    LOAD_ERR_SIZE = 2,
    LOAD_ERR_MAGIC = 3,
    LOAD_ERR_VERSION = 4,
    LOAD_ERR_DIMS = 5,
    LOAD_ERR_CRC = 6
};

inline const char* load_error_str(int r) {
    switch (r) {
        case LOAD_OK: return "ok";
        case LOAD_ERR_OPEN: return "dosya acilmadi";
        case LOAD_ERR_SIZE: return "boyut uyumsuz";
        case LOAD_ERR_MAGIC: return "magic uyumsuz";
        case LOAD_ERR_VERSION: return "versiyon uyumsuz";
        case LOAD_ERR_DIMS: return "boyut alani uyumsuz";
        case LOAD_ERR_CRC: return "CRC uyumsuz";
        default: return "bilinmeyen";
    }
}

// CRC32 (poly 0xEDB88320), tablo uretimli — harici bagimlilik yok.
inline uint32_t crc32(const uint8_t* data, size_t len) {
    uint32_t table[256];
    for (uint32_t i = 0; i < 256; ++i) {
        uint32_t c = i;
        for (int k = 0; k < 8; ++k)
            c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        table[i] = c;
    }
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; ++i)
        crc = table[(crc ^ data[i]) & 0xFFu] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}

inline void put_u32le(std::vector<uint8_t>& b, uint32_t v) {
    b.push_back((uint8_t)(v & 0xFFu));
    b.push_back((uint8_t)((v >> 8) & 0xFFu));
    b.push_back((uint8_t)((v >> 16) & 0xFFu));
    b.push_back((uint8_t)((v >> 24) & 0xFFu));
}

inline void put_i32le(std::vector<uint8_t>& b, int32_t v) {
    put_u32le(b, (uint32_t)v);
}

inline uint32_t get_u32le(const uint8_t* p) {
    return ((uint32_t)p[0]) | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

struct Sums {
    int64_t wsum;
    int64_t tsum;
    int64_t rsum;
};

// Ogrenilmis state toplamlari (test telemetrisi; duruma etkisi YOK).
inline Sums state_sums(V4cUnit* u, V4cK4Net& net, bool k4_on) {
    Sums s;
    s.wsum = 0;
    s.tsum = 0;
    s.rsum = 0;
    for (int i = 0; i < P3X3_N; ++i) {
        for (int k = 0; k < P3X3_NSYN; ++k) {
            const Synapse* sn = p3x3_syn(u[i].base, k);
            s.wsum += (int64_t)sn->weight;
            s.tsum += (int64_t)sn->trace;
        }
    }
    if (k4_on) {
        for (int a = 0; a < V4C_NB; ++a)
            for (int b = 0; b < V4C_NB; ++b)
                s.rsum += (int64_t)net.r[a][b];
    }
    return s;
}

// Save: basarida 0, dosyada hata varsa 1. Ogrenme hesabina etkisi YOK.
inline int state_save(const char* path, V4cUnit* u, V4cK4Net& net,
                      uint32_t last_tick) {
    std::vector<uint8_t> b;
    b.reserve(TOTAL_LEN);
    put_u32le(b, MAGIC);
    put_u32le(b, VERSION);
    put_u32le(b, (uint32_t)P3X3_N);
    put_u32le(b, (uint32_t)P3X3_NSYN);
    put_u32le(b, (uint32_t)V4C_NB);
    put_u32le(b, last_tick);
    put_u32le(b, 0u);  // flags
    put_u32le(b, 0u);  // reserved
    for (int i = 0; i < P3X3_N; ++i)
        for (int k = 0; k < P3X3_NSYN; ++k)
            put_i32le(b, p3x3_syn(u[i].base, k)->weight);
    for (int i = 0; i < P3X3_N; ++i)
        for (int k = 0; k < P3X3_NSYN; ++k)
            put_i32le(b, p3x3_syn(u[i].base, k)->trace);
    for (int a = 0; a < V4C_NB; ++a)
        for (int b2 = 0; b2 < V4C_NB; ++b2)
            put_i32le(b, net.r[a][b2]);
    uint32_t crc = crc32(b.data(), b.size());
    put_u32le(b, crc);
    if (b.size() != TOTAL_LEN) return 1;  // ic tutarlilik (olmamali)
    FILE* f = fopen(path, "wb");
    if (!f) return 1;
    size_t n = fwrite(b.data(), 1, b.size(), f);
    fclose(f);
    return (n == b.size()) ? 0 : 1;
}

struct StateMeta {
    uint32_t last_tick;
};

// Load: tum dogrulamalar gecmeden state'e DOKUNULMAZ.
// Donus LoadResult; LOAD_OK disinda cagiran temiz baslar.
inline int state_load(const char* path, V4cUnit* u, V4cK4Net& net,
                      bool k4_on, StateMeta* meta) {
    FILE* f = fopen(path, "rb");
    if (!f) return LOAD_ERR_OPEN;
    std::vector<uint8_t> b;
    b.reserve(TOTAL_LEN + 16);
    uint8_t chunk[4096];
    size_t n;
    while ((n = fread(chunk, 1, sizeof(chunk), f)) > 0)
        b.insert(b.end(), chunk, chunk + n);
    fclose(f);
    if (b.size() != TOTAL_LEN) return LOAD_ERR_SIZE;
    if (get_u32le(&b[0]) != MAGIC) return LOAD_ERR_MAGIC;
    if (get_u32le(&b[4]) != VERSION) return LOAD_ERR_VERSION;
    if (get_u32le(&b[8]) != (uint32_t)P3X3_N ||
        get_u32le(&b[12]) != (uint32_t)P3X3_NSYN ||
        get_u32le(&b[16]) != (uint32_t)V4C_NB)
        return LOAD_ERR_DIMS;
    uint32_t want = crc32(b.data(), TOTAL_LEN - 4);
    if (get_u32le(&b[TOTAL_LEN - 4]) != want) return LOAD_ERR_CRC;
    // Dogrulama tamam — simdi uygula (kismi yukleme imkansiz).
    if (meta) meta->last_tick = get_u32le(&b[20]);
    size_t off = HEADER_LEN;
    for (int i = 0; i < P3X3_N; ++i) {
        for (int k = 0; k < P3X3_NSYN; ++k) {
            int32_t w = (int32_t)get_u32le(&b[off]);
            off += 4;
            p3x3_syn(u[i].base, k)->weight = w;
        }
    }
    for (int i = 0; i < P3X3_N; ++i) {
        for (int k = 0; k < P3X3_NSYN; ++k) {
            int32_t t = (int32_t)get_u32le(&b[off]);
            off += 4;
            if (t < 0) t = 0;
            if (t > (int32_t)FIXED_ONE) t = FIXED_ONE;
            p3x3_syn(u[i].base, k)->trace = t;
        }
    }
    if (k4_on) {
        for (int a = 0; a < V4C_NB; ++a) {
            for (int b2 = 0; b2 < V4C_NB; ++b2) {
                int32_t r = (int32_t)get_u32le(&b[off]);
                off += 4;
                if (r < 0) r = 0;
                if (r > (int32_t)FIXED_ONE) r = FIXED_ONE;
                net.r[a][b2] = r;
            }
        }
    }
    return LOAD_OK;
}

}  // namespace plstate

#endif  // PATTERN_STATE_H