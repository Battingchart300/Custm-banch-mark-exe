// HardwareInfo.cs - zistovanie info o hardveri v C#, prepis z Python verzie PTS Benchmark.
// Windows only (WMI + PerformanceCounter + nvidia-smi). Bez otvarania konzoly:
// vsetky pomocne procesy bezia s CreateNoWindow = true.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Management;
using System.Text.RegularExpressions;

namespace PtsHardwareInfo
{
    public static class HardwareInfo
    {
        // ---------- Pomocne: spustenie prikazu na pozadi, bez konzoly ----------
        public static string RunCmd(string fileName, string arguments)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = fileName,
                    Arguments = arguments,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden,
                };
                using var p = Process.Start(psi);
                if (p == null) return "";
                string outText = p.StandardOutput.ReadToEnd();
                p.WaitForExit(8000);
                return (outText ?? "").Trim();
            }
            catch
            {
                return "";
            }
        }

        // ---------- WMI pomocne ----------
        private static string? WmiFirst(string query, string property, string? scope = null)
        {
            try
            {
                var searcher = scope == null
                    ? new ManagementObjectSearcher(query)
                    : new ManagementObjectSearcher(scope, query);
                foreach (ManagementObject obj in searcher.Get())
                {
                    var v = obj[property];
                    if (v != null) return v.ToString();
                }
            }
            catch { }
            return null;
        }

        private static List<Dictionary<string, object?>> WmiAll(string query, string? scope = null)
        {
            var list = new List<Dictionary<string, object?>>();
            try
            {
                var searcher = scope == null
                    ? new ManagementObjectSearcher(query)
                    : new ManagementObjectSearcher(scope, query);
                foreach (ManagementObject obj in searcher.Get())
                {
                    var d = new Dictionary<string, object?>();
                    foreach (var prop in obj.Properties)
                        d[prop.Name] = prop.Value;
                    list.Add(d);
                }
            }
            catch { }
            return list;
        }

        // ---------- System info (ako system_info() v Pythone) ----------
        public static string CpuName() =>
            WmiFirst("SELECT Name FROM Win32_Processor", "Name") ?? "Neznáme CPU";

        public static int CpuCores() => Environment.ProcessorCount;

        public static double RamTotalGb()
        {
            try
            {
                string? s = WmiFirst("SELECT TotalPhysicalMemory FROM Win32_ComputerSystem", "TotalPhysicalMemory");
                if (s != null && ulong.TryParse(s, out ulong bytes))
                    return Math.Round(bytes / 1024.0 / 1024.0 / 1024.0, 1);
            }
            catch { }
            return 0;
        }

        public static (string Name, double VramGb) GpuInfo()
        {
            try
            {
                string? name = WmiFirst("SELECT Name FROM Win32_VideoController", "Name");
                string? mem = WmiFirst("SELECT AdapterRAM FROM Win32_VideoController", "AdapterRAM");
                double vram = 0;
                if (mem != null && ulong.TryParse(mem, out ulong b))
                    vram = Math.Round(b / 1024.0 / 1024.0 / 1024.0, 1);
                // nvidia-smi da presnejsiu VRAM
                string smi = RunCmd("nvidia-smi",
                    "--query-gpu=memory.total --format=csv,noheader,nounits");
                if (!string.IsNullOrWhiteSpace(smi) &&
                    double.TryParse(smi.Split('\n')[0].Trim(),
                        NumberStyles.Any, CultureInfo.InvariantCulture, out double mb))
                    vram = Math.Round(mb / 1024.0, 1);
                return (name ?? "Neznáme GPU", vram);
            }
            catch
            {
                return ("Neznáme GPU", 0);
            }
        }

        public static string OsInfo() =>
            WmiFirst("SELECT Caption FROM Win32_OperatingSystem", "Caption") ?? Environment.OSVersion.ToString();

        public static double DiskUsedPct()
        {
            try
            {
                string root = Path.GetPathRoot(Directory.GetCurrentDirectory()) ?? "C:\\";
                var drive = new DriveInfo(root);
                if (drive.TotalSize <= 0) return 0;
                return Math.Round((1.0 - (double)drive.AvailableFreeSpace / drive.TotalSize) * 100, 1);
            }
            catch { return 0; }
        }

        public static Dictionary<string, object?> SystemInfo()
        {
            var (gpu, vram) = GpuInfo();
            return new Dictionary<string, object?>
            {
                ["CPU"] = CpuName(),
                ["Cores"] = CpuCores(),
                ["RAM_GB"] = RamTotalGb(),
                ["GPU"] = gpu,
                ["VRAM_GB"] = vram,
                ["OS"] = OsInfo(),
                ["DiskUsedPct"] = DiskUsedPct(),
            };
        }

        // ---------- Zatazenie (ako get_cpu_load / get_ram_load v Pythone) ----------
        private static PerformanceCounter? _cpuCounter;
        private static PerformanceCounter? _ramCounter;

        public static double? CpuLoad()
        {
            try
            {
                _cpuCounter ??= new PerformanceCounter("Processor", "% Processor Time", "_Total");
                // Prve citanie je vzdy 0 - treba 2 citania
                _cpuCounter.NextValue();
                System.Threading.Thread.Sleep(200);
                return Math.Round(_cpuCounter.NextValue(), 1);
            }
            catch { return null; }
        }

        public static double? RamLoad()
        {
            try
            {
                _ramCounter ??= new PerformanceCounter("Memory", "% Committed Bytes In Use");
                return Math.Round(_ramCounter.NextValue(), 1);
            }
            catch { return null; }
        }

        // ---------- Teplota CPU (ako get_cpu_temp() v Pythone) ----------
        // Poradie: Libre/OpenHardwareMonitor -> WMI ThermalZone -> Perf Counters.
        // Pravda: Windows teplotu CPU standardne neposkytuje - bez
        // LibreHardwareMonitor vacsina PC vrati null. Vid README.
        public static double? CpuTemp()
        {
            // 1) LibreHardwareMonitor / OpenHardwareMonitor
            foreach (string ns in new[] { @"root\LibreHardwareMonitor", @"root\OpenHardwareMonitor" })
            {
                try
                {
                    var rows = WmiAll(
                        "SELECT Name, Value FROM Sensor WHERE SensorType = 'Temperature'", ns);
                    foreach (var row in rows)
                    {
                        string name = row.TryGetValue("Name", out var n) ? (n?.ToString() ?? "") : "";
                        if (name.Contains("CPU", StringComparison.OrdinalIgnoreCase) &&
                            row.TryGetValue("Value", out var v) &&
                            double.TryParse(v?.ToString(), NumberStyles.Any,
                                CultureInfo.InvariantCulture, out double t) &&
                            t > 0 && t < 130)
                            return Math.Round(t, 1);
                    }
                }
                catch { }
            }
            // 2) WMI MSAcpi_ThermalZoneTemperature (desatiny Kelvina)
            try
            {
                var rows = WmiAll(
                    "SELECT CurrentTemperature FROM MSAcpi_ThermalZoneTemperature",
                    @"root\wmi");
                foreach (var row in rows)
                {
                    if (row.TryGetValue("CurrentTemperature", out var v) &&
                        double.TryParse(v?.ToString(), out double k))
                    {
                        double c = k / 10.0 - 273.15;
                        if (c > 0 && c < 130) return Math.Round(c, 1);
                    }
                }
            }
            catch { }
            // 3) Win32_PerfFormattedData ThermalZoneInformation
            try
            {
                string outText = RunCmd("powershell", "-NoProfile -Command " +
                    "\"Get-CimInstance Win32_PerfFormattedData_Counters_ThermalZoneInformation " +
                    "| Select-Object -First 1 -ExpandProperty Temperature\"");
                if (double.TryParse(outText.Split('\n')[0].Trim(),
                        NumberStyles.Any, CultureInfo.InvariantCulture, out double t)
                    && t > 0 && t < 130)
                    return Math.Round(t, 1);
            }
            catch { }
            return null;
        }

        // ---------- GPU teplota + zatazenie (NVIDIA cez nvidia-smi) ----------
        public static (double? Temp, double? Load) GpuStats()
        {
            string smi = RunCmd("nvidia-smi",
                "--query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader,nounits");
            if (string.IsNullOrWhiteSpace(smi)) return (null, null);
            var parts = smi.Split(',');
            if (parts.Length < 2) return (null, null);
            double? temp = double.TryParse(parts[0].Trim(), NumberStyles.Any,
                CultureInfo.InvariantCulture, out double t) ? t : null;
            double? load = double.TryParse(parts[1].Trim(), NumberStyles.Any,
                CultureInfo.InvariantCulture, out double l) ? l : null;
            return (temp, load);
        }
    }
}
