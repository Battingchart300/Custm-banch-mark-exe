# PTS Hardware Info — C# prepis

Zisťovanie info o hardvéri z PTS Benchmarku, prepísané z Pythonu do C# (.NET 8, Windows only).

## Čo to robí (rovnako ako Python verzia)

- **System info:** CPU meno + počet jadier, RAM celkom, GPU meno + VRAM, OS, disk obsadený %
- **Zaťaženie:** CPU % a RAM % cez PerformanceCounter
- **Teplota CPU:** LibreHardwareMonitor / OpenHardwareMonitor (WMI) → WMI ThermalZone → Perf Counters
- **GPU teplota + zaťaženie:** NVIDIA cez `nvidia-smi`
- **Žiadne blikajúce konzoly:** všetky pomocné procesy bežia s `CreateNoWindow = true`

## Build (na Windows)

```bat
cd csharp
dotnet build -c Release
```

Výstup: `bin\Release\net8.0-windows\PtsHardwareInfo.exe`

Alebo priamo spustiť:

```bat
dotnet run -c Release
dotnet run -c Release -- --live
dotnet run -c Release -- --json
```

## Použitie

```bat
PtsHardwareInfo.exe            :: vypíše info raz (text + JSON)
PtsHardwareInfo.exe --live     :: každé 2 s: CPU/GPU teplota a zaťaženie
PtsHardwareInfo.exe --json     :: len JSON
```

## Teplota CPU — úprimne

Windows teplotu CPU štandardne vôbec neposkytuje. Ak appka napíše "nedá sa zistiť":
1. Stiahni LibreHardwareMonitor (portable, zadarmo)
2. Spusti ho a nechaj bežať na pozadí
3. Spusti PtsHardwareInfo znova — teplota sa objaví

## Súbory

- `HardwareInfo.cs` — celá detekcia (WMI, PerformanceCounter, nvidia-smi)
- `Program.cs` — výpis text + JSON, `--live` režim
- `PtsHardwareInfo.csproj` — .NET 8 Windows, balíčky System.Management + System.Diagnostics.PerformanceCounter
