"""Prosedürel salep üreteci — saf Python, deterministik .obj çıktısı.

Neden prosedürel (Adım 4): her görsel kanal bir skalere bağlanır
(ölçek/eğim/renk), rig/blend-shape gerekmez, lisans riski yok,
repoda versiyonlanır, headless test edilir (G13).

Parçalar: yaprak (mızraksı şerit) · yumru (ölçekli küre) ·
kök lifleri (tohumlu demet, 4-gen kesitli konik tüpler) ·
sap (konik tüp) · çiçek (miğfer + 3 loblu dudak + mahmuz).

Kullanım: cd salep_core && .venv/bin/python -m sim.models.salep_gen
Çıktı: sim/models/*.obj (üçgen yüzler + yumuşak normaller).

Anayasa: sunum katmanıdır, fizik iddiası içermez (§0).
"""
import math
import os
import random

VERSION = 1
SEED = 7001
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


class Mesh:
    """Üçgen mesh: 0-bazlı verteks + yüz listesi."""

    def __init__(self):
        self.v = []  # [(x, y, z)]
        self.f = []  # [(i, j, k)]

    def add_vert(self, p):
        self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.v) - 1

    def add_tri(self, a, b, c):
        self.f.append((a, b, c))

    def add_quad(self, a, b, c, d):
        self.f.extend([(a, b, c), (a, c, d)])

    def merge(self, other):
        off = len(self.v)
        self.v.extend(other.v)
        self.f.extend([(a + off, b + off, c + off) for a, b, c in other.f])
        return self

    def xform(self, fn):
        self.v = [fn(p) for p in self.v]
        return self

    def weld(self, eps=1e-9):
        """Aynı konumlu verteksleri birleştir, sıfır-alanlı yüzleri at.

        Kutup/sivri-uç şeritleri tek noktaya çöker (delik bırakmaz).
        QSSG dejenere üçgen içeren dosyayı toptan reddeder ("Mesh file
        invalid") — bu metot o sınıfı kökten kapatır. Deterministik
        (eklenme sırası korunur).
        """
        key_of = {}
        remap = []
        new_v = []
        for p in self.v:
            key = (round(p[0] / eps), round(p[1] / eps), round(p[2] / eps))
            if key in key_of:
                remap.append(key_of[key])
            else:
                key_of[key] = len(new_v)
                remap.append(len(new_v))
                new_v.append(p)
        new_f = []
        for a, b, c in self.f:
            ra, rb, rc = remap[a], remap[b], remap[c]
            if len({ra, rb, rc}) == 3:
                new_f.append((ra, rb, rc))
        self.v = new_v
        self.f = new_f
        return self

    def compute_normals(self):
        """Newell yüz normallerinden yumuşak verteks normalleri."""
        acc = [[0.0, 0.0, 0.0] for _ in self.v]
        for a, b, c in self.f:
            pa, pb, pc = self.v[a], self.v[b], self.v[c]
            ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
            vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
            nx, ny, nz = (uy * vz - uz * vy, uz * vx - ux * vz,
                          ux * vy - uy * vx)
            for i in (a, b, c):
                acc[i][0] += nx
                acc[i][1] += ny
                acc[i][2] += nz
        out = []
        for n in acc:
            L = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
            out.append((0.0, 1.0, 0.0) if L == 0 else
                       (n[0] / L, n[1] / L, n[2] / L))
        return out

    def write_obj(self, path, name):
        # Qt Quick 3D (QSSG) `f v//vn` formunu reddeder ("Mesh file
        # invalid") → düzlemsel uv + tam `f v/vt/vn` yazılır.
        self.weld()
        normals = self.compute_normals()
        xs = [p[0] for p in self.v]
        ys = [p[1] for p in self.v]
        dx = max(xs) - min(xs) or 1.0
        dy = max(ys) - min(ys) or 1.0
        uvs = [((p[0] - min(xs)) / dx, (p[1] - min(ys)) / dy)
               for p in self.v]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# salep_gen.py v{VERSION} seed={SEED} part={name}\n")
            for p in self.v:
                fh.write(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
            for u, v in uvs:
                fh.write(f"vt {u:.6f} {v:.6f}\n")
            for n in normals:
                fh.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
            for a, b, c in self.f:  # 1:1:1 sıra (v/vt/vn)
                fh.write(f"f {a + 1}/{a + 1}/{a + 1} "
                         f"{b + 1}/{b + 1}/{b + 1} "
                         f"{c + 1}/{c + 1}/{c + 1}\n")
        return len(self.v), len(self.f)


def mat_translate(dx, dy, dz):
    return lambda p: (p[0] + dx, p[1] + dy, p[2] + dz)


def mat_scale(sx, sy, sz):
    return lambda p: (p[0] * sx, p[1] * sy, p[2] * sz)


def mat_rot_y(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return lambda p: (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


def ellipsoid(rx, ry, rz, nu=10, nv=8, exp=1.0):
    """Kapalı ölçekli küre (yumru, dudak lobları için).

    exp: süper-elipsoid üssü (1.0=küre, <1 kutumsu, >1 sivri).
    """
    def shp(x):
        return math.copysign(abs(x) ** exp, x) if x != 0 else 0.0
    m = Mesh()
    idx = {}
    for iu in range(nu + 1):
        th = math.pi * iu / nu
        for iv in range(nv + 1):
            ph = 2 * math.pi * iv / nv
            idx[(iu, iv)] = m.add_vert((
                rx * shp(math.sin(th) * math.cos(ph)),
                ry * shp(math.cos(th)),
                rz * shp(math.sin(th) * math.sin(ph))))
    for iu in range(nu):
        for iv in range(nv):
            m.add_quad(idx[(iu, iv)], idx[(iu + 1, iv)],
                       idx[(iu + 1, iv + 1)], idx[(iu, iv + 1)])
    return m


def bezier(p0, p1, p2, p3, t):
    """Kübik Bézier (yaprak genişlik/hat profili için)."""
    u = 1 - t
    return (u ** 3 * p0 + 3 * u * u * t * p1
            + 3 * u * t * t * p2 + t ** 3 * p3)


def leaf(length=1.0, width=0.30, nu=48, nv=14, fold=0.35, arch=0.12,
         droop=0.25):
    """Mızraksı yaprak: Bézier genişlik profili, V-kat, kemer, sarkma."""
    m = Mesh()
    idx = {}
    for iu in range(nu + 1):
        u = iu / nu
        # Genişlik: Bézier (dar dip → %40'ta karın → sivri uç)
        w = width * 0.5 * bezier(0.12, 0.95, 1.0, 0.0, min(1.0, u * 1.02))
        cx = bezier(0.0, 0.06, -0.04, 0.0, u)  # orta damar hattı
        x = (u - 0.45) * length
        for iv in range(nv + 1):
            vv = iv / nv * 2 - 1
            y = vv * w + cx * w
            z = fold * abs(vv) * w + arch * math.sin(math.pi * u) \
                - droop * u ** 3
            idx[(iu, iv)] = m.add_vert((x, y, z))
    for iu in range(nu):
        for iv in range(nv):
            m.add_quad(idx[(iu, iv)], idx[(iu, iv + 1)],
                       idx[(iu + 1, iv + 1)], idx[(iu + 1, iv)])
    return m


def tuber(rx=0.16, ry=0.22, rz=0.16):
    return ellipsoid(rx, ry, rz, nu=36, nv=26, exp=0.85)


def tube(points, r0, r1, sides=4):
    """Çokgen kesitli konik tüp (sap, mahmuz, kök lifi)."""
    m = Mesh()
    n = len(points)
    # tüp eksenine dik çerçeve: ardışık fark + sabit yukarı referansı
    rings = []
    for s, p in enumerate(points):
        q = points[min(s + 1, n - 1)]
        dx, dy, dz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        dx, dy, dz = dx / L, dy / L, dz / L
        # referans: eksene dik ilk vektör
        rx, ry, rz = (0.0, 1.0, 0.0) if abs(dy) < 0.9 else (1.0, 0.0, 0.0)
        ux = ry * dz - rz * dy
        uy = rz * dx - rx * dz
        uz = rx * dy - ry * dx
        ul = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / ul, uy / ul, uz / ul
        vx = dy * uz - dz * uy
        vy = dz * ux - dx * uz
        vz = dx * uy - dy * ux
        r = r0 + (r1 - r0) * s / max(1, n - 1)
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ring.append(m.add_vert((
                p[0] + r * (math.cos(a) * ux + math.sin(a) * vx),
                p[1] + r * (math.cos(a) * uy + math.sin(a) * vy),
                p[2] + r * (math.cos(a) * uz + math.sin(a) * vz))))
        rings.append(ring)
    for s in range(n - 1):
        for k in range(sides):
            m.add_quad(rings[s][k], rings[s][(k + 1) % sides],
                       rings[s + 1][(k + 1) % sides], rings[s + 1][k])
    # uç kapağı (yelpaze)
    tip = m.add_vert(points[-1])
    for k in range(sides):
        m.add_tri(rings[-1][k], rings[-1][(k + 1) % sides], tip)
    return m


def stem(height=1.0, r_base=0.045, r_top=0.025):
    pts = [(0.0, height * s / 14, 0.0) for s in range(15)]
    return tube(pts, r_base, r_top, sides=16)


def _fiber_points(rng, ang, tilt, L, spread, phase, segs=20):
    pts = []
    for s in range(segs + 1):
        t = s / segs
        rr = spread * t * tilt
        pts.append((
            math.cos(ang) * rr + 0.03 * math.sin(t * 5 + phase),
            -L * t,
            math.sin(ang) * rr + 0.03 * math.cos(t * 4 + phase * 2)))
    return pts


def root_bundle(n=16, length=0.55, spread=0.30, seed=SEED):
    """Kök demeti: L-sistem-lite — ana lif + her lifte 1 yan dal.

    Tohumlu yön/sallantı/uzunluk; aşağı-dışa konik tüpler.
    """
    rng = random.Random(seed)
    m = Mesh()
    for i in range(n):
        ang = 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        tilt = rng.uniform(0.25, 0.75)
        L = length * rng.uniform(0.7, 1.15)
        pts = _fiber_points(rng, ang, tilt, L, spread, float(i), segs=20)
        m.merge(tube(pts, 0.016, 0.002, sides=8))
        # Yan dal: orta boğumdan yarı uzunlukta, açılı
        mid = pts[len(pts) // 2]
        b_ang = ang + rng.uniform(0.5, 1.2)
        b_pts = [(mid[0] + (math.cos(b_ang) * spread * 0.4 * t
                            + 0.02 * math.sin(t * 6 + i)),
                  mid[1] - L * 0.45 * t,
                  mid[2] + (math.sin(b_ang) * spread * 0.4 * t
                            + 0.02 * math.cos(t * 5 + i)))
                 for t in [s / 8 for s in range(9)]]
        m.merge(tube(b_pts, 0.008, 0.001, sides=6))
    return m


def flower(scale=1.0):
    """Basitleştirilmiş salep çiçeği: miğfer + 3 loblu dudak + mahmuz."""
    m = Mesh()
    # Miğfer: üst yarım-küre kabuğu (önü açık)
    helm = Mesh()
    nu, nv = 32, 24
    idx = {}
    for iu in range(nu + 1):
        th = (math.pi * 0.55) * iu / nu
        for iv in range(nv + 1):
            ph = math.pi * 1.35 * (iv / nv - 0.5)  # ±~122° açıklık
            idx[(iu, iv)] = helm.add_vert((
                0.30 * math.sin(th) * math.sin(ph),
                0.34 * math.cos(th),
                -0.30 * math.sin(th) * math.cos(ph)))
    for iu in range(nu):
        for iv in range(nv):
            helm.add_quad(idx[(iu, iv)], idx[(iu, iv + 1)],
                          idx[(iu + 1, iv + 1)], idx[(iu + 1, iv)])
    helm.xform(mat_translate(0.0, 0.42, 0.02))
    m.merge(helm)
    # Dudak: 3 yassı lob (orta büyük, yanlar küçük)
    lip_mid = ellipsoid(0.16, 0.05, 0.22, nu=24, nv=18)
    lip_mid.xform(mat_translate(0.0, 0.10, 0.20))
    m.merge(lip_mid)
    for side in (-1, 1):
        lobe = ellipsoid(0.10, 0.04, 0.13, nu=18, nv=14)
        lobe.xform(mat_rot_y(side * 38))
        lobe.xform(mat_translate(side * 0.17, 0.12, 0.14))
        m.merge(lobe)
    # Mahmuz: geriye-aşağı konik tüp
    spur = tube([(0.0, 0.12, -0.05), (0.0, 0.02, -0.22),
                 (0.0, -0.06, -0.34)], 0.035, 0.008, sides=6)
    m.merge(spur)
    m.xform(mat_scale(scale, scale, scale))
    return m


PARTS = {
    "salep_leaf": lambda: leaf(),
    "salep_tuber": lambda: tuber(),
    "salep_root": lambda: root_bundle(),
    "salep_stem": lambda: stem(),
    "salep_flower": lambda: flower(),
}


def generate(out_dir=OUT_DIR):
    stats = {}
    for name, build in PARTS.items():
        path = os.path.join(out_dir, name + ".obj")
        nv, nf = build().write_obj(path, name)
        stats[name] = (nv, nf)
        print(f"  {name}.obj: {nv} verteks, {nf} yüz")
    return stats


def mesh_arrays(mesh):
    """Mesh → Godot ArrayMesh dizileri (VERTEX/NORMAL/TEX_UV/INDEX)."""
    mesh.weld()
    normals = mesh.compute_normals()
    xs = [p[0] for p in mesh.v]
    ys = [p[1] for p in mesh.v]
    dx = max(xs) - min(xs) or 1.0
    dy = max(ys) - min(ys) or 1.0
    return {
        "vertex": [c for p in mesh.v for c in p],
        "normal": [c for n in normals for c in n],
        "uv": [c for p in mesh.v
               for c in ((p[0] - min(xs)) / dx, (p[1] - min(ys)) / dy)],
        "index": [i for f in mesh.f for i in f],
    }


def generate_json(out_dir=OUT_DIR):
    """salep_meshes.json — Godot runtime ArrayMesh kaynağı (R1).

    Editör importu yok, binary asset yok; tek doğruluk kaynağı bu dosya.
    """
    import json
    parts = {}
    for name, build in PARTS.items():
        a = mesh_arrays(build())
        parts[name] = {**a, "tris": len(a["index"]) // 3}
    doc = {"meta": {"version": VERSION, "seed": SEED,
                    "format": "world_arrays.v1"},
           "parts": parts}
    path = os.path.join(out_dir, "salep_meshes.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    counts = {n: p["tris"] for n, p in parts.items()}
    print(f"  salep_meshes.json: {counts}")
    return path


def generate_tex(out_dir=None):
    """Prosedürel dokular (DÜRÜST NOT: fotoğraf yok — salep benekleri
    prosedürel beneklenir; Anacamptis morio betimlemesine dayalı stil,
    ölçü değil).
    """
    import numpy as np
    out_dir = out_dir or os.path.join(OUT_DIR, "tex")
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(SEED)

    def spots(base, n, rmin, rmax, color, size=256):
        img = np.ones((size, size, 3)) * np.asarray(base)
        yy, xx = np.mgrid[0:size, 0:size]
        for _ in range(n):
            cx, cy = rng.integers(0, size, 2)
            r = rng.uniform(rmin, rmax)
            m = (xx - cx) ** 2 + (yy - cy) ** 2 < r * r
            img[m] = color
        return np.clip(img, 0, 1)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # Yaprak albedo: yeşil gradyan + koyu mor benekler + açık orta damar
    leaf = spots([0.24, 0.55, 0.20], 90, 3, 9, [0.30, 0.16, 0.28])
    leaf[:, 124:132] = [0.45, 0.68, 0.35]
    leaf *= np.linspace(0.85, 1.05, 256)[None, :, None]
    plt.imsave(os.path.join(out_dir, "leaf_albedo.png"),
               np.clip(leaf, 0, 1))
    plt.imsave(os.path.join(out_dir, "leaf_roughness.png"),
               np.full((128, 128), 0.62))
    # Yumru albedo: açık kahve benekli
    tuber = spots([0.72, 0.58, 0.38], 60, 2, 7, [0.55, 0.42, 0.26],
                  size=128)
    plt.imsave(os.path.join(out_dir, "tuber_albedo.png"),
               np.clip(tuber, 0, 1))
    # Toprak albedo: koyu kahve taneli
    soil = spots([0.30, 0.20, 0.13], 400, 1, 3, [0.42, 0.30, 0.19],
                 size=256)
    plt.imsave(os.path.join(out_dir, "soil_albedo.png"),
               np.clip(soil, 0, 1))
    print(f"  tex/: 4 PNG (prosedürel)")
    return out_dir


def main():
    print(f"salep_gen v{VERSION} (seed={SEED}) → {OUT_DIR}")
    generate()
    generate_json()
    generate_tex()


if __name__ == "__main__":
    main()
