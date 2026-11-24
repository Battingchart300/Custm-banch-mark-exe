# PTS Benchmark v1.2.0

Benchmark app pre Windows 10 / 11 — CPU + RAM + Disk + GPU + Stress test v jednom .exe.

## Čo meria

- **CPU** — single-core a multi-core, matematika v slučke (3 s na test)
- **RAM** — rýchlosť kopírovania 64 MB bloku, MB/s
- **Disk** — zápis / čítanie 100 MB súboru, MB/s (súbor sa po teste zmaže)
- **GPU** — info (názov, VRAM, driver cez `nvidia-smi` ak je) + 2D render test, FPS
  - Pozor: GPU test je 2D, nie 3D ako 3DMark. Na integrovanej grafike bude FPS nižšie — to je normálne.
- **PTS skóre** — orientačné číslo z 4 testov, nie porovnatelné s Cinebench / 3DMark
- **Uložiť** — výsledok do .json

## Stress test (nové v 1.2.0)

- Dĺžka: 15 min / 30 min / 1 hod / 2 hod / **4 hod** / Do zastavenia
- Zaškrtni čo má zaťažovať: CPU + RAM + GPU
- Zaťažuje všetky jadrá CPU na 100 %, kopíruje RAM a renderuje GPU
- **Stop** kedykoľvek, log sa uloží do `pts_stress_log.txt`
- **Bezpečnosť:** pri 90 °C+ zastav test, pri 95 °C sa zastaví sám

## Graf teploty a zaťaženia (nové v 1.2.0)

- Živý graf, aktualizácia každé 2 s, aj bez stress testu
- zelená = zaťaženie CPU %
- červená = teplota CPU °C
- oranžová = teplota GPU °C (len NVIDIA cez `nvidia-smi`)
- **Teplota CPU na Windows:** nie každý PC ju vie dať cez WMI. Ak graf ukazuje len zaťaženie, teplota sa nedá zistiť — to je normálne, nie chyba appky.
- Pre presnejšie % CPU / RAM nainštaluj pred buildom `psutil` (voliteľné, build.bat to spraví sám).

## Ako spraviť .exe (na tvojom PC)

1. Nainštaluj Python 3.10+ z python.org (zaškrtni **Add Python to PATH**)
2. Daj `main.py` + `build.bat` do jedného priečinka, napr. `C:\PTS-Bench\`
3. Dvojklik na `build.bat`
4. Hotový exe je v `dist\PTS-Benchmark.exe`

Len štandardná knižnica + voliteľný `psutil`.
Veľkosť exe: cca 10–15 MB.

## Na školský PC

- Len stiahni .exe a spusti — žiadny Python, žiadny build.
- Dlhy stress test (2–4 h) len so súhlasom učiteľa a len keď pri PC niekto je. Školský PC nie je tvoj — nezaťažuj ho bez povolenia.
