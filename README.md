# PTS Benchmark v0.3

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
- Hore v okne vždy vidíš: `Verzia: v0.3 | Máš najnovšiu verziu` alebo `Nová verzia v0.3 je dostupná!`
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

## Stop všetko + žiadny test pri štarte (nové v 0.2)

- Tlačidlo **■ Stop všetko** zastaví CPU, RAM, Disk, GPU aj Stress test — do pár sekúnd, pri najbližšej kontrole.
- Pri štarte appky sa nespúšťa žiadny test. Testy štartujú len tlačidlom. Monitor (graf) len číta hodnoty, netestuje.

## Graf pre všetko (nové v 0.2)

- Jeden živý graf, každé 2 s: CPU % (zelená), RAM % (modrá), Disk obsadený % (fialová), GPU zaťaženie / teplota (oranžová), teplota CPU °C (červená)
- Pod grafom sú zaškrtávacie políčka Graf: CPU / RAM / Disk / GPU / Teplota — čo nechceš vidieť, odškrtni
- Aktuálne čísla aj ako text pod grafom: CPU %, RAM %, Disk obsadený %, teplota CPU, GPU

## Teplota a zaťaženie CPU / GPU (vylepšené v 0.2)

- Veľký panel hore: CPU teplota + zaťaženie %, GPU teplota + zaťaženie %, RAM %
- Zaťaženie CPU ide aj bez `psutil` — na Windows cez GetSystemTimes, na Linuxe cez /proc/stat
- Zaťaženie RAM ide aj bez `psutil` — na Windows cez GlobalMemoryStatusEx
- Teplota CPU: psutil → OpenHardwareMonitor / LibreHardwareMonitor (ak je nainštalovaný) → WMI
- Teplota + zaťaženie GPU: NVIDIA cez `nvidia-smi`
- Ak PC teplotu nedá zistiť, appka ukáže len zaťaženie a napíše "nedá sa zistiť" — nie je to chyba appky

## GPU okno (vylepšené v 0.2)

- GPU test okno aj GPU stress okno majú pevnú veľkosť, nie sú topmost a nevolá sa focus ani lift — okno zostane tam, kde je, a neskáče dopredu/dozadu.
- Zatvorenie GPU okna krížikom zastaví test (Stop všetko).

## Žiadne preblikávanie (vylepšené v 0.2)

- Aktualizuje sa LEN graf (canvas) — mriežka sa nakreslí raz a zostáva, mažú sa len dátové čiary.
- Text pod grafom sa prepíše len keď sa hodnota naozaj zmenila.
- Teplota CPU sa číta len každých 10 s, nie každé 2 s (PowerShell/WMI volanie brzdilo UI).
- `log()` ani `set_status()` už nevolajú `update_idletasks()` — to prekresľovalo celé okno a bolo hlavnou príčinou preblikávania.

## Skutočná aktualizácia (nové v 0.3)

- Keď príde nová verzia, appka to **reálne ukáže**: žltý banner hore + červený text pri verzii + okno s otázkou.
- Tlačidlo **Aktualizovať a reštartovať**: stiahne nový exe z GitHub Releases, prepíše starý a appku reštartuje. Nemusíš nič sťahovať ani mazať ručne.
- Ako to funguje: nový exe sa stiahne ako `PTS-Benchmark-update.exe`, potom `update.bat` počká 2 s, prepíše starý exe novým, spustí ho a sám sa vymaže. Bežiaci exe sa totiž nedá prepísať priamo.
- Kontrola beží pri štarte aj tlačidlom "Skontrolovať aktualizácie". Ak je test v behu, aktualizácia počká — najprv Stop všetko.
