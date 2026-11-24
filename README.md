# PTS Benchmark v0.1

Benchmark app pre Windows 10 / 11 — CPU + RAM + Disk + GPU + Stress test v jednom .exe.

## Čo meria

- **CPU** — single-core a multi-core, matematika v slučke (3 s na test)
- **RAM** — rýchlosť kopírovania 64 MB bloku, MB/s
- **Disk** — zápis / čítanie 100 MB súboru, MB/s (súbor sa po teste zmaže)
- **GPU** — info (názov, VRAM, driver cez `nvidia-smi` ak je) + 2D render test, FPS
  - Pozor: GPU test je 2D, nie 3D ako 3DMark. Na integrovanej grafike bude FPS nižšie — to je normálne.
- **PTS skóre** — orientačné číslo z 4 testov, nie porovnatelné s Cinebench / 3DMark
- **Uložiť** — výsledok do .json

## Stress test (nové v 1.2.0, vlastný čas v 1.3.0)

- Dĺžka: 15 min / 30 min / 1 hod / 2 hod / **4 hod** / Do zastavenia
- **Vlastný čas (1.3.0):** klikni do poľa s dĺžkou a napíš vlastný čas — napr. `45 min`, `90 min`, `3 hod`, `2.5 hod` (1 min – 8 hod). Zlý formát appka odmietne s hláškou.
- **Rýchly test:** vedľa tlačidla Uložiť je `Test (s):` — dĺžka CPU/RAM testu v sekundách, 1–10 s, štandardne 3 s.
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

## Kontrola aktualizácií (nové v 0.1)

- Appka pri štarte sama skontroluje GitHub Releases, či je novšia verzia.
- Hore v okne vždy vidíš: `Verzia: v0.1 | Máš najnovšiu verziu` alebo `Nová verzia v0.2 je dostupná!`
- Tlačidlo **Skontrolovať aktualizácie** skontroluje ručne.
- Ak je nová verzia, appka sa len opýta, či chceš otvoriť stránku na stiahnutie — nič sama nesťahuje ani neinštaluje.
- Nemusíš v kuse sťahovať a mazať: starý exe prepíšeš novým, až keď nová verzia naozaj vyjde.
- Bez internetu len napíše, že sa nepodarilo skontrolovať — appka normálne funguje ďalej.

## Novabench-style skóre a história (nové v 0.1)

- Po celom teste: **celkové skóre 0–1000** + podskóre CPU / RAM / Disk / GPU (každé 0–1000)
- Váhy: CPU 40 %, RAM 20 %, Disk 20 %, GPU 20 % — ako Novabench, len s našimi testami
- **História:** každý celý test sa uloží do `pts_history.json` (max 20 záznamov)
- V appke vidíš najlepšie skóre, počet testov a posledné 3 behy — porovnáš, či PC po zmene ide lepšie alebo horšie
- Výsledok sa dá uložiť aj do .json cez tlačidlo Uložiť
