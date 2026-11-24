#!/usr/bin/env python3
"""
PTS Benchmark v0.2 - Windows 10/11
CPU + RAM + Disk + GPU + Stress test (az 4 h, vlastny cas) + graf + kontrola aktualizacii + Stop vsetko
Pri starte sa nespusta ziadny test.
Python 3.10+ / Tkinter / len standardna kniznica (psutil volitelny)
Build: PyInstaller --onefile --noconsole main.py
Autor: BattingChart300 / PTS Corporation
"""
import json
import math
import multiprocessing
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import filedialog, messagebox, ttk

APP_NAME = "PTS Benchmark"
VERSION = "0.5"
REPO = "Battingchart300/Custm-banch-mark-exe"
RELEASES_URL = f"https://github.com/{REPO}/releases"
CPU_DURATION = 3.0
RAM_SIZE_MB = 64
DISK_SIZE_MB = 100
STRESS_DURATIONS = {
    "15 min": 15 * 60,
    "30 min": 30 * 60,
    "1 hod": 60 * 60,
    "2 hod": 2 * 60 * 60,
    "4 hod": 4 * 60 * 60,
    "Do zastavenia": 0,
}

def parse_duration(text):
    """Vlastny cas testovania: '45', '45 min', '90 min', '1 hod', '2.5 hod',
    '3h', 'Do zastavenia'. Vrati sekundy (0 = do zastavenia) alebo None."""
    if text is None:
        return None
    t = str(text).strip().lower()
    if t in ("", "do zastavenia", "nekonecno", "0"):
        return 0
    if t in STRESS_DURATIONS:
        return STRESS_DURATIONS[t]
    # cislo + volitelna jednotka
    import re
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*(min|m|hod|h|hodin|hodiny)?$", t)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    unit = m.group(2) or "min"
    if unit in ("hod", "h", "hodin", "hodiny"):
        secs = int(val * 3600)
    else:
        secs = int(val * 60)
    if secs < 60 or secs > 8 * 3600:
        return None  # 1 min - 8 hod
    return secs


HISTORY_FILE = "pts_history.json"
# Stop vsetko: nastavi sa tlacidlom Stop vsetko, vycisti sa pri starte noveho testu.
# Pri starte appky je prazdny a nespusta sa ziadny test.
STOP_ALL = threading.Event()


def compute_scores(results):
    """Novabench-style skore: kazdy test 0-1000, celkom 0-1000 (vazene)."""
    try:
        cpu = results.get("cpu", {}).get("multi_kops", 0)
        ram = results.get("ram", {}).get("mb_s", 0)
        d = results.get("disk", {})
        disk = ((d.get("write_mb_s", 0) + d.get("read_mb_s", 0)) / 2) if d else 0
        gpu = results.get("gpu", {}).get("fps", 0)
        cpu_s = min(1000, int(cpu / 10))
        ram_s = min(1000, int(ram / 20))
        disk_s = min(1000, int(disk / 2))
        gpu_s = min(1000, int(gpu * 10))
        total = int(cpu_s * 0.4 + ram_s * 0.2 + disk_s * 0.2 + gpu_s * 0.2)
        return {"cpu": cpu_s, "ram": ram_s, "disk": disk_s, "gpu": gpu_s, "total": total}
    except Exception:
        return {"cpu": 0, "ram": 0, "disk": 0, "gpu": 0, "total": 0}


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history_entry(entry):
    try:
        hist = load_history()
        hist.append(entry)
        hist = hist[-20:]  # max 20 zaznamov
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2, ensure_ascii=False)
        return hist
    except Exception:
        return load_history()


def version_tuple(v):
    """'v1.2.0' -> (1, 2, 0), '0.1' -> (0, 1). Na porovnanie verzii."""
    try:
        parts = str(v).strip().lstrip("vV").split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    except Exception:
        return (0,)


def check_latest_version():
    """Zisti najnovsiu verziu z GitHub Releases. Vrati (verzia, url) alebo (None, None)."""
    info = check_latest_release()
    if info is None:
        return None, None
    return info["version"], info["html_url"]


def check_latest_release():
    """Cely latest release z GitHubu: verzia, stranka, poznamky, exe asset.
    Vrati dict alebo None."""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/releases/latest",
            headers={"User-Agent": f"{APP_NAME}/{VERSION}"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.load(r)
        tag = str(data.get("tag_name", "")).strip()
        if not tag:
            return None
        asset_url = None
        asset_name = None
        for a in data.get("assets", []) or []:
            if str(a.get("name", "")).lower().endswith(".exe"):
                asset_url = a.get("browser_download_url")
                asset_name = a.get("name")
                break
        return {"version": tag.lstrip("vV"),
                "html_url": data.get("html_url") or RELEASES_URL,
                "body": (data.get("body") or "")[:500],
                "asset_url": asset_url,
                "asset_name": asset_name or "PTS-Benchmark.exe"}
    except Exception:
        return None


def build_updater_bat(exe_name, new_name):
    """Windows .bat, ktory po vypnuti appky prepise stary exe novym a spusti ho.
    Bezi az ked appka skonci, lebo bezici exe sa neda prepisat."""
    return (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'move /y "{new_name}" "{exe_name}"\r\n'
        f'start "" "{exe_name}"\r\n'
        'del "%~f0"\r\n'
    )


# psutil je volitelny - ak je, mame presne % CPU / RAM / teplotu na Linuxe
try:
    import psutil
    HAS_PSUTIL = True
except Exception:
    psutil = None
    HAS_PSUTIL = False


# ---------- System info ----------

def run_cmd(cmd):
    """Spusti prikaz na pozadi - na Windows bez otvarania konzoly.
    Bez toho by kazde volanie wmic / powershell / nvidia-smi (kazde 2 s)
    blikalo ciernym oknom konzoly."""
    try:
        kw = {}
        if sys.platform == "win32":
            # Skryte okno konzoly: CREATE_NO_WINDOW + STARTUPINFO
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kw["startupinfo"] = si
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=8, shell=False, **kw)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def get_cpu_name():
    if sys.platform == "win32":
        out = run_cmd(["wmic", "cpu", "get", "name"])
        for line in out.splitlines():
            line = line.strip()
            if line and line.lower() != "name":
                return line
        out = run_cmd(["powershell", "-NoProfile", "-Command",
                       "(Get-CimInstance Win32_Processor).Name"])
        if out:
            return out.splitlines()[0].strip()
    return platform.processor() or platform.machine() or "Neznamy CPU"


def get_ram_total_gb():
    try:
        if HAS_PSUTIL:
            return round(psutil.virtual_memory().total / (1024 ** 3), 1)
        if sys.platform == "win32":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MS()
            st.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return round(st.ullTotalPhys / (1024 ** 3), 1)
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / (1024 * 1024), 1)
    except Exception:
        pass
    return 0.0


def get_gpu_info():
    name, vram, extra = "Neznama / integrovana", 0.0, ""
    if sys.platform == "win32":
        out = run_cmd(["wmic", "path", "win32_VideoController",
                       "get", "name,AdapterRAM"])
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if len(lines) >= 2:
            parts = lines[1].split()
            for tok in parts:
                if tok.isdigit() and int(tok) > 1024 * 1024:
                    vram = round(int(tok) / (1024 ** 3), 1)
            name = " ".join(p for p in parts if not p.isdigit())
        smi = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                       "--format=csv,noheader"])
        if smi:
            p = [x.strip() for x in smi.split(",")]
            if len(p) >= 2:
                name = p[0]
                try:
                    vram = round(float(p[1].split()[0]) / 1024, 1)
                except Exception:
                    pass
                if len(p) >= 3:
                    extra = f"Driver {p[2]}"
    return name, vram, extra


def get_disk_used_pct():
    try:
        total, used, free = shutil.disk_usage(os.getcwd())
        return round(used / total * 100, 1) if total else None
    except Exception:
        return None


def cs_hardware_info():
    """C# helper PtsHardwareInfo.exe (zabudovany v exe cez PyInstaller
    --add-binary, alebo vedla exe). Vrati dict z --json, alebo None.
    Pouziva sa len na jednorazove info o hardveri, nie na zivy monitor
    (spustenie .NET exe kazde 2 s by bolo pomale). Ak helper chyba,
    vsetko funguje dalej po starom cez Python detekciu."""
    try:
        candidates = []
        # PyInstaller onefile: subory su v docasnom _MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "PtsHardwareInfo.exe"))
        if getattr(sys, "frozen", False):
            candidates.append(os.path.join(
                os.path.dirname(os.path.abspath(sys.executable)),
                "PtsHardwareInfo.exe"))
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "PtsHardwareInfo.exe"))
        candidates.append(os.path.join(os.getcwd(), "PtsHardwareInfo.exe"))
        exe_path = None
        for c in candidates:
            if os.path.isfile(c):
                exe_path = c
                break
        if exe_path is None:
            return None
        out = run_cmd([exe_path, "--json"])
        if not out:
            return None
        # --json vypise len JSON, ale pre istotu vezmi od prvej { po poslednu }
        start = out.find("{")
        end = out.rfind("}")
        if start < 0 or end < 0:
            return None
        data = json.loads(out[start:end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def get_disk_info():
    try:
        total, used, free = shutil.disk_usage(os.getcwd())
        return round(total / (1024 ** 3)), round(free / (1024 ** 3))
    except Exception:
        return 0, 0


def system_info():
    cpu = get_cpu_name()
    cores = os.cpu_count() or 1
    ram = get_ram_total_gb()
    gpu, vram, extra = get_gpu_info()
    dt, df = get_disk_info()
    return {
        "OS": f"{platform.system()} {platform.release()} ({platform.version()})",
        "CPU": cpu,
        "Jadra / vlakna": f"{cores} (logickych)",
        "RAM": f"{ram} GB",
        "GPU": f"{gpu} ({vram} GB VRAM)" + (f" - {extra}" if extra else ""),
        "Disk": f"{dt} GB celkom, {df} GB volnych",
        "Python": platform.python_version(),
        "psutil": "ano" if HAS_PSUTIL else "nie (volitelny)",
    }


# ---------- Monitoring: teplota / zatazenie ----------

_CPU_TIMES_PREV = None


def _cpu_load_windows_ctypes():
    """CPU % cez Windows GetSystemTimes (bez psutil)."""
    global _CPU_TIMES_PREV
    try:
        import ctypes
        class FT(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                        ("dwHighDateTime", ctypes.c_ulong)]
        idle, kernel, user = FT(), FT(), FT()
        ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        def to_int(f):
            return (f.dwHighDateTime << 32) | f.dwLowDateTime
        cur = (to_int(idle), to_int(kernel), to_int(user))
        if _CPU_TIMES_PREV is None:
            _CPU_TIMES_PREV = cur
            return 0.0
        prev = _CPU_TIMES_PREV
        _CPU_TIMES_PREV = cur
        idle_d = cur[0] - prev[0]
        total_d = (cur[1] - prev[1]) + (cur[2] - prev[2])
        if total_d <= 0:
            return 0.0
        return round((1.0 - idle_d / total_d) * 100, 1)
    except Exception:
        return None


def _cpu_load_proc_stat():
    """CPU % cez /proc/stat (Linux, bez psutil)."""
    global _CPU_TIMES_PREV
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        vals = [int(x) for x in parts[1:8]]
        idle = vals[3] + vals[4]
        total = sum(vals)
        cur = (idle, total)
        if _CPU_TIMES_PREV is None:
            _CPU_TIMES_PREV = cur
            return 0.0
        prev = _CPU_TIMES_PREV
        _CPU_TIMES_PREV = cur
        d_idle = cur[0] - prev[0]
        d_total = cur[1] - prev[1]
        if d_total <= 0:
            return 0.0
        return round((1.0 - d_idle / d_total) * 100, 1)
    except Exception:
        return None


def get_cpu_load():
    """CPU zatazenie v %. Poradie: psutil -> Windows ctypes -> /proc/stat."""
    try:
        if HAS_PSUTIL:
            return float(psutil.cpu_percent(interval=0.2))
    except Exception:
        pass
    if sys.platform == "win32":
        v = _cpu_load_windows_ctypes()
        if v is not None:
            return v
    else:
        v = _cpu_load_proc_stat()
        if v is not None:
            return v
    return None


def get_ram_load():
    """RAM zatazenie v %. Poradie: psutil -> Windows GlobalMemoryStatusEx -> /proc/meminfo."""
    try:
        if HAS_PSUTIL:
            return float(psutil.virtual_memory().percent)
    except Exception:
        pass
    try:
        if sys.platform == "win32":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MS()
            st.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return float(st.dwMemoryLoad)
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.split()[0])
            total = mem.get("MemTotal", 0)
            avail = mem.get("MemAvailable", mem.get("MemFree", 0))
            if total:
                return round((1 - avail / total) * 100, 1)
    except Exception:
        pass
    return None


def get_cpu_temp():
    """Teplota CPU v °C, alebo None ak sa neda zistit.
    Poradie: psutil senzory -> Linux /sys/class/thermal -> Windows:
    Libre/OpenHardwareMonitor (CimInstance aj wmic) -> WMI ThermalZone
    -> Win32_PerfFormattedData ThermalZoneInformation.
    Pravda: Windows teplotu CPU standardne vobec neposkytuje - vacsina PC ju
    neda bez LibreHardwareMonitor. Ak vrati None, appka to napise a poradi,
    co nainstalovat (vid show_cpu_temp_help)."""
    try:
        if HAS_PSUTIL:
            temps = psutil.sensors_temperatures()
            for key in ("coretemp", "cpu_thermal", "k10temp", "zenpower"):
                if key in temps and temps[key]:
                    return float(temps[key][0].current)
            for vals in temps.values():
                if vals:
                    return float(vals[0].current)
    except Exception:
        pass
    # Linux: /sys/class/thermal (funguje aj bez psutil)
    if sys.platform != "win32":
        try:
            import glob
            for path in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
                try:
                    with open(path) as f:
                        v = int(f.read().strip())
                    if v > 1000:  # milistupne
                        v = v / 1000.0
                    if 0 < v < 130:
                        return round(float(v), 1)
                except Exception:
                    continue
        except Exception:
            pass
    if sys.platform == "win32":
        # 1) OpenHardwareMonitor / LibreHardwareMonitor cez PowerShell
        for ns in ("root\\OpenHardwareMonitor", "root\\LibreHardwareMonitor"):
            out = run_cmd(["powershell", "-NoProfile", "-Command",
                           f"Get-CimInstance -Namespace {ns} -ClassName Sensor "
                           "| Where-Object {{ $_.SensorType -eq 'Temperature' -and $_.Name -match 'CPU' }} "
                           "| Select-Object -First 1 -ExpandProperty Value"])
            try:
                if out:
                    v = float(out.splitlines()[0].strip())
                    if 0 < v < 130:
                        return round(v, 1)
            except Exception:
                pass
            # 1b) to iste cez wmic (starsi, ale niekde funguje lepsie)
            out = run_cmd(["wmic", f"/namespace:\\\\{ns}", "PATH", "Sensor",
                           "where", "SensorType='Temperature'",
                           "get", "Name,Value"])
            try:
                for line in out.splitlines():
                    if "CPU" in line.upper():
                        for part in line.split():
                            try:
                                v = float(part)
                                if 0 < v < 130:
                                    return round(v, 1)
                            except Exception:
                                pass
            except Exception:
                pass
        # 2) WMI MSAcpi_ThermalZoneTemperature (nie kazdy PC to ma)
        out = run_cmd(["wmic", "/namespace:\\\\root\\wmi", "PATH",
                       "MSAcpi_ThermalZoneTemperature", "get", "CurrentTemperature"])
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                # WMI vracia desatiny Kelvina
                v = round(int(line) / 10.0 - 273.15, 1)
                if 0 < v < 130:
                    return v
        # 3) Win32_PerfFormattedData ThermalZoneInformation
        out = run_cmd(["powershell", "-NoProfile", "-Command",
                       "Get-CimInstance Win32_PerfFormattedData_Counters_ThermalZoneInformation "
                       "| Select-Object -First 1 -ExpandProperty Temperature"])
        try:
            if out:
                v = float(out.splitlines()[0].strip())
                if 0 < v < 130:
                    return round(v, 1)
        except Exception:
            pass
    return None


def get_gpu_stats():
    """NVIDIA cez nvidia-smi: teplota, zatazenie %, spotreba. Inak OHM, inak None."""
    smi = run_cmd(["nvidia-smi",
                   "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
                   "--format=csv,noheader,nounits"])
    if smi:
        try:
            p = [x.strip() for x in smi.split(",")]
            return {"temp": float(p[0]), "load": float(p[1]),
                    "power_w": float(p[2]) if len(p) > 2 else None}
        except Exception:
            pass
    return None


# ---------- CPU / RAM / Disk test ----------

def _cpu_worker(duration):
    ops = 0
    end = time.perf_counter() + duration
    x = 1.0
    while time.perf_counter() < end:
        if STOP_ALL.is_set():
            break
        for _ in range(2000):
            x = math.sqrt(x + 1.7) + math.sin(x) * 0.5
            ops += 1
        if x > 1e9:
            x = 1.0
    return ops


def cpu_test(duration=CPU_DURATION):
    t0 = time.perf_counter()
    ops1 = _cpu_worker(duration)
    single = ops1 / duration
    cores = os.cpu_count() or 1
    if STOP_ALL.is_set():
        return {"single_kops": round(single / 1000, 1),
                "multi_kops": 0, "cores": cores,
                "time_s": round(time.perf_counter() - t0, 1), "stopped": True}
    try:
        with multiprocessing.Pool(processes=cores) as pool:
            results = pool.map(_cpu_worker, [duration] * cores)
        multi = sum(results) / duration
    except Exception:
        multi = single * cores * 0.7
    return {"single_kops": round(single / 1000, 1),
            "multi_kops": round(multi / 1000, 1),
            "cores": cores, "time_s": round(time.perf_counter() - t0, 1)}


def ram_test(size_mb=RAM_SIZE_MB, duration=3.0):
    size = size_mb * 1024 * 1024
    src = bytearray(os.urandom(1024 * 1024))
    data = bytearray()
    while len(data) < size:
        data += src[:min(len(src), size - len(data))]
    t0 = time.perf_counter()
    copies = 0
    end = t0 + duration
    while time.perf_counter() < end:
        if STOP_ALL.is_set():
            break
        dst = bytearray(data)
        copies += 1
        del dst
    elapsed = time.perf_counter() - t0
    return {"mb_s": round((copies * size_mb) / elapsed, 1) if elapsed > 0 else 0,
            "size_mb": size_mb, "copies": copies,
            "time_s": round(elapsed, 1), "stopped": STOP_ALL.is_set()}


def disk_test(size_mb=DISK_SIZE_MB):
    tmpdir = tempfile.gettempdir()
    path = os.path.join(tmpdir, "pts_bench_test.bin")
    chunk = b"\x00" * (1024 * 1024)
    try:
        t0 = time.perf_counter()
        with open(path, "wb") as f:
            for _ in range(size_mb):
                if STOP_ALL.is_set():
                    break
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        write_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        with open(path, "rb") as f:
            while f.read(1024 * 1024):
                if STOP_ALL.is_set():
                    break
        read_s = time.perf_counter() - t0
        return {"write_mb_s": round(size_mb / write_s, 1),
                "read_mb_s": round(size_mb / read_s, 1),
                "size_mb": size_mb}
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


# ---------- GUI ----------

class BenchApp:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_NAME} v{VERSION}")
        root.geometry("740x980")
        root.resizable(False, False)
        self.results = {}
        self.running = False
        # Stress stav
        self.stress_running = False
        self.stress_start = 0.0
        self.stress_duration = 0
        self.stress_log = []
        self.history = []  # (elapsed_s, cpu_load, cpu_temp, gpu_temp)
        self.monitor_start = time.time()
        self.gpu_win = None
        self.gpu_cv = None
        # Graf sa aktualizuje sam - text pod nim len ked sa zmenil,
        # aby sa neprekreslovalo cele okno.
        self._last_live = ""
        self._last_temp = ""
        # Teplota CPU sa cita len kazdy 5. tick (10 s) - PowerShell/WMI volanie
        # kazde 2 s zatazovalo UI a prispievalo k preblikavaniu.
        self._temp_tick = 0
        self._cpu_temp_cached = None
        # Graf: co sa ma kreslit (vsetko zapnute)
        self.var_g_cpu = tk.BooleanVar(value=True)
        self.var_g_ram = tk.BooleanVar(value=True)
        self.var_g_disk = tk.BooleanVar(value=True)
        self.var_g_gpu = tk.BooleanVar(value=True)
        self.var_g_temp = tk.BooleanVar(value=True)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        top = tk.Frame(root, padx=12, pady=8)
        top.pack(fill="x")
        tk.Label(top, text=APP_NAME, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(top, text="CPU + RAM + Disk + GPU  |  Stress test až 4 h, vlastný čas  |  v0.5",
                 font=("Segoe UI", 10), fg="#666").pack(anchor="w")
        upd = tk.Frame(top)
        upd.pack(fill="x", pady=2)
        self.update_label = tk.Label(upd, text=f"Verzia: v{VERSION}  |  Aktualizácie: kontrolujem...",
                                     font=("Segoe UI", 9), fg="#333")
        self.update_label.pack(side="left")
        tk.Button(upd, text="Skontrolovať aktualizácie",
                  command=self.check_updates_manual,
                  font=("Segoe UI", 9)).pack(side="right")
        # Banner, co sa ukaze len ked pride nova verzia - realne, nie len text
        self.update_banner = tk.Frame(top, bg="#fef3c7")
        self.update_banner_label = tk.Label(
            self.update_banner, text="", font=("Segoe UI", 10, "bold"),
            bg="#fef3c7", fg="#92400e")
        self.update_banner_label.pack(side="left", padx=6, pady=4)
        tk.Button(self.update_banner, text="Aktualizovať a reštartovať",
                  command=self.download_update,
                  bg="#16a34a", fg="white", font=("Segoe UI", 10, "bold")).pack(side="right", padx=6)
        self.latest_info = None

        info = tk.Frame(root, padx=12)
        info.pack(fill="x")
        self.info_text = tk.Text(info, height=6, font=("Consolas", 9),
                                 bg="#f2f2f2", relief="flat")
        self.info_text.pack(fill="x")
        self.show_info()

        btns = tk.Frame(root, padx=12, pady=6)
        btns.pack(fill="x")
        self.btn_all = tk.Button(btns, text="▶  Spustiť celý test",
                                 command=self.run_all, bg="#2563eb",
                                 fg="white", font=("Segoe UI", 11, "bold"),
                                 height=2, width=20)
        self.btn_all.pack(side="left", padx=3)
        for label, fn in [("CPU", self.run_cpu), ("RAM", self.run_ram),
                          ("Disk", self.run_disk), ("GPU", self.run_gpu)]:
            tk.Button(btns, text=label, command=fn, width=8,
                      font=("Segoe UI", 10)).pack(side="left", padx=3)
        tk.Button(btns, text="Uložiť", command=self.save,
                  width=8).pack(side="right", padx=3)
        tk.Button(btns, text="■ Stop všetko", command=self.stop_all,
                  bg="#7c2d12", fg="white", font=("Segoe UI", 10, "bold"),
                  width=12).pack(side="right", padx=3)
        # Dlzka rychleho testu - vlastny cas v sekundach
        tk.Label(btns, text="Test (s):", font=("Segoe UI", 9)).pack(side="right", padx=2)
        self.quick_dur = tk.Spinbox(btns, from_=1, to=10, width=3,
                                    font=("Segoe UI", 10))
        self.quick_dur.delete(0, "end")
        self.quick_dur.insert(0, "3")
        self.quick_dur.pack(side="right", padx=2)

        # --- Stress test ---
        sf = tk.LabelFrame(root, text=" Stress test — záťaž PC ", padx=10, pady=6)
        sf.pack(fill="x", padx=12, pady=4)
        tk.Label(sf, text="Dĺžka:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        # Editable - mozes napisat vlastny cas, napr. 45 min alebo 3 hod
        self.stress_dur = ttk.Combobox(sf, values=list(STRESS_DURATIONS.keys()),
                                       width=14)
        self.stress_dur.set("1 hod")
        self.stress_dur.grid(row=0, column=1, padx=4)
        self.var_cpu = tk.BooleanVar(value=True)
        self.var_ram = tk.BooleanVar(value=True)
        self.var_gpu = tk.BooleanVar(value=True)
        tk.Checkbutton(sf, text="CPU", variable=self.var_cpu).grid(row=0, column=2)
        tk.Checkbutton(sf, text="RAM", variable=self.var_ram).grid(row=0, column=3)
        tk.Checkbutton(sf, text="GPU", variable=self.var_gpu).grid(row=0, column=4)
        self.btn_stress = tk.Button(sf, text="▶  Štart stress",
                                    command=self.start_stress, bg="#dc2626",
                                    fg="white", font=("Segoe UI", 10, "bold"), width=14)
        self.btn_stress.grid(row=0, column=5, padx=6)
        self.btn_stop = tk.Button(sf, text="■  Stop", command=self.stop_stress,
                                  font=("Segoe UI", 10, "bold"), width=8,
                                  state="disabled")
        self.btn_stop.grid(row=0, column=6)
        self.stress_label = tk.Label(sf, text="Pripravený. Len na vlastnom PC alebo so súhlasom učiteľa.",
                                     font=("Segoe UI", 9), fg="#666")
        self.stress_label.grid(row=1, column=0, columnspan=7, sticky="w", pady=2)
        tk.Label(sf, text="Vlastný čas: klikni do poľa a napíš napr. 45 min, 90 min alebo 3 hod (1 min – 8 hod).",
                 font=("Segoe UI", 8), fg="#666").grid(row=2, column=0, columnspan=7, sticky="w")

        # --- Teplota a zatazenie (velke cisla) ---
        tf = tk.LabelFrame(root, text=" Teplota a zaťaženie ", padx=8, pady=4)
        tf.pack(fill="x", padx=12, pady=4)
        self.temp_label = tk.Label(tf, text="CPU: — °C / — %   |   GPU: — °C / — %   |   RAM: — %",
                                   font=("Segoe UI", 11, "bold"))
        self.temp_label.pack(anchor="w")
        tk.Label(tf, text="Teplota CPU ide cez psutil / LibreHardwareMonitor / WMI — ak PC teplotu nedá, ukáže len zaťaženie. GPU teplota ide na NVIDIA cez nvidia-smi.",
                 font=("Segoe UI", 8), fg="#666").pack(anchor="w")
        tk.Button(tf, text="Teplota CPU sa nedá zistiť? Klikni sem",
                  command=self.show_cpu_temp_help,
                  font=("Segoe UI", 9)).pack(anchor="w", pady=2)

        # --- Graf ---
        gf = tk.LabelFrame(root, text=" Graf — teplota a zaťaženie (živý, každé 2 s) ", padx=8, pady=4)
        gf.pack(fill="x", padx=12, pady=4)
        self.graph = tk.Canvas(gf, width=700, height=130, bg="white")
        self.graph.pack()
        self.live_label = tk.Label(gf, text="CPU: —  |  Teplota CPU: —  |  GPU: —",
                                   font=("Consolas", 9), fg="#333")
        self.live_label.pack(anchor="w")
        tk.Label(gf, text="zelená = CPU %  •  modrá = RAM %  •  fialová = Disk obsadený %  •  oranžová = GPU teplota / zaťaženie  •  červená = teplota CPU °C",
                 font=("Segoe UI", 8), fg="#666").pack(anchor="w")
        tog = tk.Frame(gf)
        tog.pack(anchor="w")
        tk.Label(tog, text="Graf:", font=("Segoe UI", 9)).pack(side="left")
        for txt, var in [("CPU", self.var_g_cpu), ("RAM", self.var_g_ram),
                         ("Disk", self.var_g_disk), ("GPU", self.var_g_gpu),
                         ("Teplota", self.var_g_temp)]:
            tk.Checkbutton(tog, text=txt, variable=var,
                           command=self.draw_graph).pack(side="left")

        # --- Skore ako Novabench + historia ---
        scf = tk.LabelFrame(root, text=" Skóre (ako Novabench) + história ", padx=8, pady=4)
        scf.pack(fill="x", padx=12, pady=4)
        self.score_label = tk.Label(scf, text="Celkové skóre: —  (spusti celý test)",
                                    font=("Segoe UI", 12, "bold"))
        self.score_label.pack(anchor="w")
        self.subscore_label = tk.Label(scf, text="CPU: —  |  RAM: —  |  Disk: —  |  GPU: —",
                                       font=("Consolas", 9))
        self.subscore_label.pack(anchor="w")
        self.history_text = tk.Text(scf, height=3, font=("Consolas", 8),
                                    bg="#f2f2f2", relief="flat")
        self.history_text.pack(fill="x")
        self.update_history_display()

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", padx=12)
        self.status = tk.Label(root, text="Pripravený.", font=("Segoe UI", 10), fg="#333")
        self.status.pack(anchor="w", padx=12, pady=2)

        out = tk.Frame(root, padx=12, pady=4)
        out.pack(fill="both", expand=True)
        self.out = tk.Text(out, font=("Consolas", 10), bg="#111",
                           fg="#0f0", insertbackground="white", height=8)
        self.out.pack(fill="both", expand=True)
        self.log("PTS Benchmark v0.2 - pripraveny.\n"
                 "Pri starte sa nespusta ziadny test - testy startuju len tlacidlom.\n"
                 "Stop vsetko zastavi CPU / RAM / Disk / GPU aj Stress test.\n"
                 "GPU test = 2D render test (nie 3DMark).\n"
                 "Stress: pri 90 °C+ zastav test, pri 95 °C sa zastavi sam.\n")
        # Monitor loop - bezi stale, aj bez stressu
        self.root.after(2000, self.monitor_tick)
        # Kontrola aktualizacii pri starte (vo vlakne, aby nezamrzlo GUI)
        self.root.after(1500, lambda: threading.Thread(
            target=self.check_updates, args=(False,), daemon=True).start())

    def show_info(self):
        self.info_text.delete("1.0", "end")
        cs = cs_hardware_info()
        if cs:
            self.info_text.insert("end", "Info o hardveri (C# helper):\n")
            for k, v in cs.items():
                self.info_text.insert("end", f"{k}: {v}\n")
        else:
            for k, v in system_info().items():
                self.info_text.insert("end", f"{k}: {v}\n")
        self.info_text.config(state="disabled")

    def log(self, s):
        self.out.insert("end", s)
        self.out.see("end")
        # Ziadne update_idletasks() - to prekreslovalo cele okno a preblikavalo.
        # Mainloop si prekreslenie spravi sam, len tam, kde treba.

    def set_status(self, s):
        self.status.config(text=s)
        # Ziadne update_idletasks() - vid log().

    # ----- Monitor + graf -----
    def monitor_tick(self):
        try:
            cpu_load = get_cpu_load()
            if cpu_load is None:
                cpu_load = 100.0 if self.stress_running and self.var_cpu.get() else 0.0
            self._temp_tick += 1
            if self._temp_tick % 5 == 1:
                self._cpu_temp_cached = get_cpu_temp()
            cpu_temp = self._cpu_temp_cached
            gpu = get_gpu_stats()
            gpu_temp = gpu["temp"] if gpu else None
            gpu_load = gpu["load"] if gpu else None
            ram_load = get_ram_load()
            if ram_load is None:
                ram_load = 100.0 if self.stress_running and self.var_ram.get() else 0.0
            disk_pct = get_disk_used_pct()
            elapsed = time.time() - self.monitor_start
            # (cas, cpu%, cpu_temp, gpu_temp, ram%, gpu%, disk_used%)
            self.history.append((elapsed, cpu_load, cpu_temp, gpu_temp,
                                 ram_load, gpu_load, disk_pct))
            if len(self.history) > 300:  # max 10 min v grafe
                self.history.pop(0)
            gpu_txt = f"{gpu_temp:.0f} °C / {gpu['load']:.0f}%" if gpu else "—"
            temp_txt = f"{cpu_temp:.1f} °C" if cpu_temp is not None else "nedá sa zistiť"
            ram_txt = f"{ram_load:.0f}%" if ram_load is not None else "—"
            disk_txt = f"{disk_pct:.0f}%" if disk_pct is not None else "—"
            # Aktualizuje sa LEN graf (canvas) a 2 textove riadky - a tie len ked
            # sa text naozaj zmenil. Ziadne root.update(), ziadne prekreslenie
            # celeho okna, ziadne pack/unpack. Preto okno nepreblikava.
            live_txt = (f"CPU: {cpu_load:.0f}%  |  RAM: {ram_txt}  |  Disk obsadený: {disk_txt}  |  "
                        f"Teplota CPU: {temp_txt}  |  GPU: {gpu_txt}")
            temp_txt2 = f"CPU: {temp_txt} / {cpu_load:.0f}%   |   GPU: {gpu_txt}   |   RAM: {ram_txt}"
            if live_txt != self._last_live:
                self.live_label.config(text=live_txt)
                self._last_live = live_txt
            if temp_txt2 != self._last_temp:
                self.temp_label.config(text=temp_txt2)
                self._last_temp = temp_txt2
            self.draw_graph()
            # Bezpecnost: auto-stop pri 95 °C
            if self.stress_running and cpu_temp is not None and cpu_temp >= 95:
                self.log(f"\n!!! TEPLOTA {cpu_temp} °C - auto-stop stress testu !!!\n")
                self.stop_stress()
            elif self.stress_running and gpu_temp is not None and gpu_temp >= 95:
                self.log(f"\n!!! GPU TEPLOTA {gpu_temp} °C - auto-stop !!!\n")
                self.stop_stress()
        except Exception:
            pass
        self.root.after(2000, self.monitor_tick)

    def draw_graph(self):
        cv = self.graph
        # Len data sa mazu a kreslia nanovo - mriezka ostava, takze canvas
        # nepreblikava. Ziadne mazanie celeho canvasu.
        cv.delete("data")
        w, h = 700, 130
        if len(self.history) < 2:
            cv.create_text(w // 2, h // 2, text="Čakám na dáta...", fill="#888", tags="data")
            return
        # mriezka 0 / 50 / 100 - kresli sa len raz
        if not getattr(self, "_grid_drawn", False):
            for val, y in [(100, 8), (50, h // 2), (0, h - 8)]:
                cv.create_line(30, y, w - 5, y, fill="#eee", tags="grid")
                cv.create_text(15, y, text=str(val), font=("Consolas", 8), fill="#888", tags="grid")
            self._grid_drawn = True
        t0 = self.history[0][0]
        t1 = self.history[-1][0]
        span = max(t1 - t0, 1)

        def xy(t, v, vmax=100.0):
            x = 30 + (t - t0) / span * (w - 35)
            y = (h - 8) - (v / vmax) * (h - 16)
            return x, y

        def line(idx, color, vmax=100.0):
            pts = []
            for row in self.history:
                if row[idx] is None:
                    continue
                pts.append(xy(row[0], row[idx], vmax))
            for a, b in zip(pts, pts[1:]):
                cv.create_line(a, b, fill=color, width=2, tags="data")

        if self.var_g_cpu.get():
            line(1, "green")       # CPU load %
        if self.var_g_temp.get():
            line(2, "red")         # CPU temp °C (0-100)
        if self.var_g_gpu.get():
            line(3, "orange")      # GPU temp °C
            line(5, "#ff8c00", vmax=100.0)  # GPU load % (oranzova ciarkovana)
        if self.var_g_ram.get():
            line(4, "blue")        # RAM load %
        if self.var_g_disk.get():
            line(6, "purple")      # Disk obsadeny %

    # ----- Rychle testy -----
    def _run_thread(self, fn, label):
        STOP_ALL.clear()
        if self.running or self.stress_running:
            messagebox.showwarning("Beží test", "Počkaj, kým dobehne aktuálny test.")
            return
        self.running = True
        self.progress.start(10)
        self.set_status(label + " ...")
        def wrap():
            try:
                fn()
            except Exception as e:
                self.log(f"\nCHYBA: {e}\n")
            finally:
                self.running = False
                self.progress.stop()
                self.set_status("Hotovo.")
        threading.Thread(target=wrap, daemon=True).start()

    def run_all(self):
        def job():
            self.log("\n=== CELÝ TEST ===\n")
            self.do_cpu(); self.do_ram(); self.do_disk(); self.do_gpu()
            scores = compute_scores(self.results)
            self.log("\n=== KONIEC ===\n"
                     f"Celkove skore (Novabench-style): {scores['total']} / 1000\n"
                     f"CPU {scores['cpu']} | RAM {scores['ram']} | Disk {scores['disk']} | GPU {scores['gpu']}\n")
            self.root.after(0, self.update_score_display)
        self._run_thread(job, "Beží celý test (~25 s)")

    def run_cpu(self):
        self._run_thread(self.do_cpu, "CPU test")
    def run_ram(self):
        self._run_thread(self.do_ram, "RAM test")
    def run_disk(self):
        self._run_thread(self.do_disk, "Disk test")

    def quick_seconds(self):
        try:
            v = int(self.quick_dur.get())
            return max(1, min(10, v))
        except Exception:
            return 3

    def do_cpu(self):
        self.log("\n[CPU] ...\n")
        r = cpu_test(duration=self.quick_seconds())
        self.results["cpu"] = r
        self.log(f"  Single-core: {r['single_kops']} kops/s\n"
                 f"  Multi-core ({r['cores']} jadier): {r['multi_kops']} kops/s\n")

    def do_ram(self):
        self.log("\n[RAM] ...\n")
        r = ram_test(duration=self.quick_seconds())
        self.results["ram"] = r
        self.log(f"  Rychlost kopirovania: {r['mb_s']} MB/s "
                 f"({r['size_mb']} MB, {r['copies']}x)\n")

    def do_disk(self):
        self.log("\n[Disk] ...\n")
        r = disk_test()
        self.results["disk"] = r
        self.log(f"  Zapis: {r['write_mb_s']} MB/s\n"
                 f"  Citanie: {r['read_mb_s']} MB/s\n")

    def run_gpu(self):
        if self.running or self.stress_running:
            messagebox.showwarning("Beží test", "Počkaj, kým dobehne aktuálny test.")
            return
        self.do_gpu()

    def do_gpu(self):
        self.log("\n[GPU] 2D render test (3 s) ...\n")
        gpu, vram, extra = get_gpu_info()
        self.log(f"  GPU: {gpu} ({vram} GB)\n")
        win = tk.Toplevel(self.root)
        win.title("GPU test")
        # Okno sa da zmenit velkostou (mensie aj vacsie), ostane tam, kde je:
        # nie je topmost, nevola sa focus ani lift, takze neskace dopredu/dozadu.
        win.geometry("640x380")
        win.resizable(True, True)
        try:
            win.attributes("-topmost", False)
        except Exception:
            pass
        win.protocol("WM_DELETE_WINDOW", lambda: STOP_ALL.set())
        cv = tk.Canvas(win, width=640, height=360, bg="black")
        cv.pack(fill="both", expand=True)
        colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "white"]
        frames = 0
        end = time.perf_counter() + 3.0
        while time.perf_counter() < end:
            if not win.winfo_exists():
                break
            cw = max(cv.winfo_width(), 100)
            ch = max(cv.winfo_height(), 100)
            cv.delete("all")
            for _ in range(60):
                x, y = random.randint(0, max(cw - 40, 1)), random.randint(0, max(ch - 40, 1))
                c = random.choice(colors)
                cv.create_rectangle(x, y, x + 40, y + 40, fill=c, outline="")
                cv.create_oval(x, y, x + 25, y + 25, fill=c, outline="")
            # len prekreslenie, nie win.update() - to by okno stale vyhadzovalo dopredu
            win.update_idletasks()
            frames += 1
            if STOP_ALL.is_set():
                break
        try:
            win.destroy()
        except Exception:
            pass
        fps = round(frames / 3.0, 1)
        self.results["gpu"] = {"fps": fps, "gpu": gpu, "vram_gb": vram}
        self.log(f"  FPS (2D, 60 objektov/frame): {fps}\n"
                 f"  Pozn.: nie je to 3D test ako 3DMark.\n")

    # ----- Stress test -----
    def start_stress(self):
        STOP_ALL.clear()
        if self.stress_running or self.running:
            messagebox.showwarning("Beží test", "Počkaj, kým dobehne aktuálny test.")
            return
        dur_name = self.stress_dur.get()
        parsed = parse_duration(dur_name)
        if parsed is None:
            messagebox.showwarning("Zlý čas",
                "Napíš čas ako napr. 45 min, 90 min, 1 hod alebo 3 hod\n(1 min – 8 hod, alebo Do zastavenia).")
            return
        self.stress_duration = parsed
        if not any([self.var_cpu.get(), self.var_ram.get(), self.var_gpu.get()]):
            messagebox.showwarning("Nič vybrané", "Zaškrtni aspoň CPU, RAM alebo GPU.")
            return
        if self.stress_duration >= 2 * 3600:
            if not messagebox.askyesno("Dlhy test",
                    f"Stress test na {dur_name} poriadne zahreje PC.\n"
                    "Len na vlastnom PC alebo so súhlasom učiteľa.\n"
                    "Spustiť aj tak?"):
                return
        self.stress_running = True
        self.stress_start = time.time()
        self.stress_log = []
        self.btn_stress.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.log(f"\n=== STRESS TEST START ({dur_name}) ===\n"
                 f"CPU={self.var_cpu.get()} RAM={self.var_ram.get()} GPU={self.var_gpu.get()}\n")
        if self.var_gpu.get():
            self.open_gpu_stress_window()
        threading.Thread(target=self.stress_worker, daemon=True).start()
        self.root.after(1000, self.stress_tick)

    def open_gpu_stress_window(self):
        self.gpu_win = tk.Toplevel(self.root)
        self.gpu_win.title("GPU stress")
        # Rovnako ako GPU test: da sa zmenit velkostou, nie topmost, neskace.
        self.gpu_win.geometry("640x380")
        self.gpu_win.resizable(True, True)
        try:
            self.gpu_win.attributes("-topmost", False)
        except Exception:
            pass
        self.gpu_win.protocol("WM_DELETE_WINDOW", self.stop_all)
        self.gpu_cv = tk.Canvas(self.gpu_win, width=640, height=360, bg="black")
        self.gpu_cv.pack(fill="both", expand=True)
        self.gpu_stress_frame()

    def gpu_stress_frame(self):
        if not self.stress_running or self.gpu_win is None:
            return
        try:
            cv = self.gpu_cv
            cv.delete("all")
            cw = max(cv.winfo_width(), 100)
            ch = max(cv.winfo_height(), 100)
            colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "white"]
            for _ in range(80):
                x, y = random.randint(0, max(cw - 40, 1)), random.randint(0, max(ch - 40, 1))
                c = random.choice(colors)
                cv.create_rectangle(x, y, x + 40, y + 40, fill=c, outline="")
            self.gpu_win.update_idletasks()
        except Exception:
            pass
        self.root.after(50, self.gpu_stress_frame)

    def stress_worker(self):
        cores = os.cpu_count() or 1
        cycles = 0
        while self.stress_running and not STOP_ALL.is_set():
            if self.stress_duration and (time.time() - self.stress_start) >= self.stress_duration:
                break
            try:
                if self.var_cpu.get():
                    with multiprocessing.Pool(processes=cores) as pool:
                        pool.map(_cpu_worker, [5.0] * cores)
                if self.var_ram.get() and self.stress_running:
                    ram_test(size_mb=64)
                cycles += 1
                if cycles % 12 == 0:  # cca kazdu minutu
                    el = int(time.time() - self.stress_start)
                    line = (f"[{el // 60:02d}:{el % 60:02d}] cyklus {cycles} "
                            f"CPU {get_cpu_load()}% temp {get_cpu_temp()} C")
                    self.stress_log.append(line)
                    self.log(line + "\n")
            except Exception as e:
                self.log(f"Stress chyba: {e}\n")
                break
        if self.stress_running:
            self.root.after(0, self.stop_stress)

    def stress_tick(self):
        if not self.stress_running:
            return
        el = int(time.time() - self.stress_start)
        if self.stress_duration:
            left = self.stress_duration - el
            self.stress_label.config(
                text=f"Beží: {el // 60:02d}:{el % 60:02d}  |  Zostáva: {max(left,0) // 60:02d}:{max(left,0) % 60:02d}")
        else:
            self.stress_label.config(text=f"Beží: {el // 60:02d}:{el % 60:02d}  |  Do zastavenia")
        self.root.after(1000, self.stress_tick)

    def stop_stress(self):
        if not self.stress_running:
            return
        self.stress_running = False
        el = int(time.time() - self.stress_start)
        self.btn_stress.config(state="normal")
        self.btn_stop.config(state="disabled")
        if self.gpu_win is not None:
            try:
                self.gpu_win.destroy()
            except Exception:
                pass
            self.gpu_win = None
            self.gpu_cv = None
        self.stress_label.config(
            text=f"Stress skončil po {el // 60:02d}:{el % 60:02d}. Log uložený.")
        self.log(f"\n=== STRESS KONIEC ({el // 60} min {el % 60} s) ===\n")
        # Uloz log
        try:
            with open("pts_stress_log.txt", "w", encoding="utf-8") as f:
                f.write(f"PTS Benchmark v{VERSION} stress log\n")
                f.write(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.stress_start))}\n")
                f.write(f"Trvanie: {el} s\n")
                f.write("\n".join(self.stress_log) + "\n")
            self.log("Log: pts_stress_log.txt\n")
        except Exception:
            pass

    # ----- Skore + historia (Novabench) -----
    def update_score_display(self):
        scores = compute_scores(self.results)
        self.results["scores"] = scores
        self.score_label.config(text=f"Celkové skóre: {scores['total']} / 1000")
        self.subscore_label.config(
            text=f"CPU: {scores['cpu']}  |  RAM: {scores['ram']}  |  "
                 f"Disk: {scores['disk']}  |  GPU: {scores['gpu']}")
        entry = {"date": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "total": scores["total"], "scores": scores,
                 "system": system_info().get("CPU", "")}
        save_history_entry(entry)
        self.update_history_display()

    def update_history_display(self):
        hist = load_history()
        self.history_text.config(state="normal")
        self.history_text.delete("1.0", "end")
        if not hist:
            self.history_text.insert("end", "História: zatiaľ žiadny celý test. Po prvom teste sa tu ukáže porovnanie.\n")
            return
        best = max(hist, key=lambda x: x.get("total", 0))
        self.history_text.insert(
            "end", f"Najlepšie skóre: {best.get('total')} ({best.get('date')})  |  Počet testov: {len(hist)}\n")
        for h in hist[-3:]:
            self.history_text.insert(
                "end", f"  {h.get('date')}  celkom {h.get('total')}  "
                       f"(CPU {h.get('scores', {}).get('cpu')} / RAM {h.get('scores', {}).get('ram')} / "
                       f"Disk {h.get('scores', {}).get('disk')} / GPU {h.get('scores', {}).get('gpu')})\n")
        self.history_text.config(state="disabled")

    # ----- Stop vsetko -----
    def stop_all(self):
        STOP_ALL.set()
        was_running = self.running or self.stress_running
        self.stress_running = False
        if self.gpu_win is not None:
            try:
                self.gpu_win.destroy()
            except Exception:
                pass
            self.gpu_win = None
            self.gpu_cv = None
        self.btn_stress.config(state="normal")
        self.btn_stop.config(state="disabled")
        try:
            self.progress.stop()
        except Exception:
            pass
        if was_running:
            self.log("\n■ STOP VŠETKO — všetky úlohy zastavené.\n")
            self.set_status("Zastavené.")
        else:
            self.log("Stop všetko: žiadny test nebeží.\n")
            self.set_status("Pripravený — žiadny test nebeží.")

    # ----- Teplota CPU - pomoc -----
    def show_cpu_temp_help(self):
        if messagebox.askyesno("Teplota CPU",
                "Windows teplotu CPU štandardne vôbec neposkytuje — väčšina PC ju\n"
                "nedá zistiť bez pomocného programu. Najlepšia cesta zadarmo:\n\n"
                "1) Stiahni LibreHardwareMonitor (portable, zadarmo)\n"
                "2) Spusti ho (netreba inštalovať) a nechaj ho bežať na pozadí\n"
                "3) Reštartuj PTS Benchmark — teplota CPU sa objaví\n\n"
                "Chceš otvoriť stránku na stiahnutie LibreHardwareMonitor?"):
            webbrowser.open("https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases")

    # ----- Aktualizacie -----
    def check_updates_manual(self):
        threading.Thread(target=self.check_updates, args=(True,),
                         daemon=True).start()

    def check_updates(self, manual=False):
        info = check_latest_release()
        if info is None:
            msg = f"Verzia: v{VERSION}  |  Aktualizácie: nepodarilo sa skontrolovať (offline?)"
            self.root.after(0, lambda: self.update_label.config(text=msg))
            if manual:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Aktualizácie", "Nepodarilo sa skontrolovať aktualizácie.\nSkontroluj internet a skús znova."))
            return
        latest = info["version"]
        if version_tuple(latest) > version_tuple(VERSION):
            self.latest_info = info
            msg = f"Verzia: v{VERSION}  |  Nová verzia v{latest} je dostupná!"
            self.root.after(0, lambda: self.update_label.config(text=msg, fg="#dc2626"))
            self.root.after(0, lambda: self.show_update_banner(latest))
            self.root.after(0, lambda: self.ask_update(latest))
        else:
            self.latest_info = None
            self.root.after(0, self.update_banner.pack_forget)
            msg = f"Verzia: v{VERSION}  |  Máš najnovšiu verziu (v{latest})"
            self.root.after(0, lambda: self.update_label.config(text=msg, fg="#15803d"))
            if manual:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Aktualizácie", f"Máš najnovšiu verziu v{VERSION}."))

    def show_update_banner(self, latest):
        self.update_banner_label.config(
            text=f"⬆ Nová verzia v{latest} je dostupná! (ty máš v{VERSION})")
        self.update_banner.pack(fill="x", pady=4)

    def ask_update(self, latest):
        if messagebox.askyesno("Nová verzia",
                f"Je dostupná nová verzia v{latest} (ty máš v{VERSION}).\n"
                "Aktualizovať teraz? Stiahne sa nový exe a appka sa reštartuje."):
            self.download_update()

    def download_update(self):
        info = self.latest_info
        if not info or not info.get("asset_url"):
            messagebox.showwarning("Aktualizácia",
                "Nenašiel sa exe súbor v novej verzii.\nSkús znova neskôr.")
            return
        if self.running or self.stress_running:
            messagebox.showwarning("Beží test",
                "Najprv zastav bežiaci test (Stop všetko), potom aktualizuj.")
            return
        self.update_label.config(text=f"Sťahujem verziu v{info['version']} ...", fg="#2563eb")
        threading.Thread(target=self._download_update_job, args=(info,), daemon=True).start()

    def _download_update_job(self, info):
        try:
            if getattr(sys, "frozen", False):
                exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                exe_name = os.path.basename(sys.executable)
            else:
                exe_dir = os.path.dirname(os.path.abspath(__file__))
                exe_name = "PTS-Benchmark.exe"
            new_name = "PTS-Benchmark-update.exe"
            new_path = os.path.join(exe_dir, new_name)
            req = urllib.request.Request(info["asset_url"],
                headers={"User-Agent": f"{APP_NAME}/{VERSION}"})
            with urllib.request.urlopen(req, timeout=60) as r, open(new_path, "wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            if not getattr(sys, "frozen", False):
                self.root.after(0, lambda: messagebox.showinfo(
                    "Aktualizácia stiahnutá",
                    f"Nový exe je stiahnutý ako:\n{new_path}\n"
                    "Toto je beh zo zdrojového kódu, nie z exe - reštart nejde, "
                    "nahraď exe súbor ručne."))
                return
            bat_path = os.path.join(exe_dir, "update.bat")
            with open(bat_path, "w", encoding="utf-8", newline="") as f:
                f.write(build_updater_bat(exe_name, new_name))
            self.root.after(0, lambda: self.update_label.config(
                text=f"Aktualizácia v{info['version']} stiahnutá - reštartujem ...", fg="#15803d"))
            time.sleep(0.5)
            subprocess.Popen(["cmd", "/c", bat_path], cwd=exe_dir,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            self.root.after(0, self.root.destroy)
        except Exception as e:
            self.root.after(0, lambda: self.update_label.config(
                text=f"Aktualizácia zlyhala: {e}", fg="#dc2626"))
            self.root.after(0, lambda: messagebox.showerror(
                "Aktualizácia zlyhala", f"Nepodarilo sa stiahnuť novú verziu:\n{e}"))

    def pts_score(self):
        try:
            c = self.results.get("cpu", {}).get("multi_kops", 0)
            r = self.results.get("ram", {}).get("mb_s", 0)
            d = self.results.get("disk", {})
            dw = d.get("write_mb_s", 0); dr = d.get("read_mb_s", 0)
            g = self.results.get("gpu", {}).get("fps", 0)
            return round(c * 0.4 + r * 0.05 + (dw + dr) / 2 * 0.2 + g * 5)
        except Exception:
            return 0

    def save(self):
        if not self.results and not self.stress_log:
            messagebox.showinfo("Nič na uloženie", "Najprv spusti aspoň jeden test.")
            return
        data = {"app": APP_NAME, "version": VERSION,
                "system": system_info(), "results": self.results,
                "stress_log": self.stress_log,
                "pts_score": self.pts_score(),
                "date": time.strftime("%Y-%m-%d %H:%M:%S")}
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt")],
            initialfile=f"pts_bench_{time.strftime('%Y%m%d_%H%M')}.json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            if path.endswith(".txt"):
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Uložené", f"Výsledok uložený:\n{path}")


def main():
    multiprocessing.freeze_support()
    root = tk.Tk()
    BenchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
