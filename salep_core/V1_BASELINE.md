# v1 Baseline Manifestosu (§9.85) — 2026-09-15

"İşte mevcut sensory lobe böyle çalışıyor." Bu dosya + anayasa
§9.85, v1 referansıdır. Degisiklikte bu hash'ler karsilastirilir.

## Kod (donmus)

8253df005c20699902d558971ea848d0  src/sensory_lobe.h
b93156e0e4bfdb92ba6989be7c95313a  src/main_sensory_plant.cpp
adcd431f026fdcb2d6965e4e64c8b2a4  sim/electro.py
db2455970826e9513407d46b42427cfd  sim/assoc.py
6dd33b8e2a0408a2424e2b4361ffb72c  sim/plant_sim.py
45314bc943923e4130f83a2806477020  sim/sensor_map.py
f8915effdc104eb71ef7bf734469b0ea  validate_testb.py
b7fa5417fc2f0b315184a8058ef46acd  validate_condition_sweep.py
8f455070ec1a3ac1c5f63ce2d67700af  validate_plir.py
d34d75e21f19be0f8f943d77579b71d7  validate_assoc.py
9907b5584cb34b9b13d4d827dbcc56f7  validate_inference.py
d3ff965420ef8c3494004e5b3e7f6101  validate_quadratic_assoc.py
3e44595075f6c905a7cccc50e5bf4007  npu_sensory_plant (binary)

## Artefakt (salt-okunur referans)

781c33552f3dc91147101b18af5b82f4  testb_spikes.csv
e29a257dac84d3292d5c2e31de4ec06f  testb_sensors.csv
36900401a13822a77cb13fe921931526  testb_conditions.csv
92f8c6a48b1c5f646ff4a83a3d1bca5e  testb_afferent.csv
970aa7e3377368c3ba38e4c961b7ab02  testb_membrane.csv
f1b2c606014d03320a474aedf9ecf11f  plir_decisions.csv
c6b62ec44e7e2aa6f81e43bcd81322c  sensory_raster.csv
1298ecc045c39262a2492b5c2d73dfdc  sensory_sequences.csv
3eef013edf8731e5756a3959f7270c52  sensory_signatures.csv

## Referans skorlar (donmus)

- OZET-TESTB: B1..B4+B6 + B5_CR_YOK (§9.59)
- OZET-ASSOC: S1..S5, 163/165 = %98.8 (§9.62)
- OZET-COND-SWEEP: D1..D5 (§9.65)
- OZET-INFER-1: 97/175 = 0.554, kurak->N 28/28 (§9.68)
- OZET-QUAD-ASSOC: 70/175 = 0.400 (sabit nokta, §9.71/§9.79)
- Temsil tavani: agirlikli saflik 0.920, 123/175 distinct (§9.81)
- Forensic: B-ailesi sikisma, 3/3 B1 (§9.84)

## Yol haritasi notu (kullanici karari)

1. v1 kilitli (bu dosya). 2. Learning motoru bunun USTUNE baglanir
   (SENSORY→REPRESENTATION→LEARNING→MEMORY), bagimsiz test edilir;
   quadratic adaydir ama kotu performansi sensory compression
   karisikligindan AYRILMALIDIR (acik metodolojik borc). 3. Loba
   mudahale yalniz downstream zorunlulukta, kontrollu ve kucuk
   (orn. P1→A/B aktarimi); bastan-yazma YOK.
