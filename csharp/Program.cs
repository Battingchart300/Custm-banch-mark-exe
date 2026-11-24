// Program.cs - PTS Benchmark hardware info v C#
// Pouzitie:
//   PtsHardwareInfo.exe            - vypise info raz (text + JSON)
//   PtsHardwareInfo.exe --live     - kazde 2 s: CPU/GPU teplota a zatazenie (ako monitor v Pythone)
//   PtsHardwareInfo.exe --json     - len JSON
using System;
using System.Text.Json;
using PtsHardwareInfo;

bool live = Array.Exists(args, a => a == "--live");
bool jsonOnly = Array.Exists(args, a => a == "--json");

if (live)
{
    Console.WriteLine("PTS Hardware Info - live (Ctrl+C na zastavenie)");
    while (true)
    {
        double? cpuLoad = HardwareInfo.CpuLoad();
        double? ramLoad = HardwareInfo.RamLoad();
        double? cpuTemp = HardwareInfo.CpuTemp();
        var (gpuTemp, gpuLoad) = HardwareInfo.GpuStats();
        string cpuTempTxt = cpuTemp.HasValue ? $"{cpuTemp:F1} °C" : "nedá sa zistiť";
        string gpuTxt = gpuTemp.HasValue ? $"{gpuTemp:F0} °C / {gpuLoad:F0}%" : "—";
        Console.WriteLine(
            $"CPU: {cpuLoad?.ToString("F0") ?? "—"}%  |  RAM: {ramLoad?.ToString("F0") ?? "—"}%  |  " +
            $"Disk obsadený: {HardwareInfo.DiskUsedPct():F0}%  |  Teplota CPU: {cpuTempTxt}  |  GPU: {gpuTxt}");
        System.Threading.Thread.Sleep(2000);
    }
}

var info = HardwareInfo.SystemInfo();
info["CpuLoadPct"] = (object?)HardwareInfo.CpuLoad();
info["RamLoadPct"] = (object?)HardwareInfo.RamLoad();
info["CpuTempC"] = (object?)HardwareInfo.CpuTemp();
var (gt, gl) = HardwareInfo.GpuStats();
info["GpuTempC"] = (object?)gt;
info["GpuLoadPct"] = (object?)gl;

if (!jsonOnly)
{
    Console.WriteLine("=== PTS Benchmark - Hardware Info (C#) ===");
    foreach (var kv in info)
        Console.WriteLine($"{kv.Key}: {kv.Value ?? "—"}");
    if (info["CpuTempC"] == null)
    {
        Console.WriteLine();
        Console.WriteLine("Teplota CPU sa nedá zistiť: Windows ju štandardne neposkytuje.");
        Console.WriteLine("Spusti LibreHardwareMonitor na pozadí a spusti znova - potom sa objaví.");
    }
    Console.WriteLine();
    Console.WriteLine("=== JSON ===");
}

string json = JsonSerializer.Serialize(info, new JsonSerializerOptions { WriteIndented = true });
Console.WriteLine(json);
