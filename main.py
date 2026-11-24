#!/usr/bin/env python3
"""
PTS Benchmark v1.2.0 - Windows 10/11
CPU + RAM + Disk + GPU + Stress test (az 4 h) + graf teploty / zatazenia
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
from tkinter import filedialog, messagebox, ttk

APP_NAME = "PTS Benchmark"
VERSION = "1.2.0"
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

# psutil je volitelny - ak je, mame presne % CPU / RAM / teplotu na Linuxe
try:
    import psutil
    HAS_PSUTIL = True
except Exception:
    psutil = None
    HAS_PSUTIL = False


# ---------- System info ----------

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=8, shell=False)
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

def get_cpu_load():
    """CPU zatazenie v %. psutil = presne, inak odhad z nasho stressu."""
    try:
        if HAS_PSUTIL:
            return float(psutil.cpu_percent(interval=0.2))
    except Exception:
        pass
    return None


def get_ram_load():
    try:
        if HAS_PSUTIL:
            return float(psutil.virtual_memory().percent)
    except Exception:
        pass
    return None


def get_cpu_temp():
    """Teplota CPU v °C, alebo None ak sa neda zistit.
    Windows: WMI MSAcpi_ThermalZoneTemperature (nie kazdy PC to ma).
    Linux + psutil: sensors_temperatures().
    NVIDIA GPU teplota ide cez nvidia-smi - vid get_gpu_stats()."""
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
    if sys.platform == "win32":
        out = run_cmd(["wmic", "/namespace:\\\\root\\wmi", "PATH",
                       "MSAcpi_ThermalZoneTemperature", "get", "CurrentTemperature"])
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                # WMI vracia desatiny Kelvina
                return round(int(line) / 10.0 - 273.15, 1)
    return None


def get_gpu_stats():
    """NVIDIA: teplota, zatazenie %, spotreba. Inak None."""
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
    try:
        with multiprocessing.Pool(processes=cores) as pool:
            results = pool.map(_cpu_worker, [duration] * cores)
        multi = sum(results) / duration
    except Exception:
        multi = single * cores * 0.7
    return {"single_kops": round(single / 1000, 1),
            "multi_kops": round(multi / 1000, 1),
            "cores": cores, "time_s": round(time.perf_counter() - t0, 1)}


def ram_test(size_mb=RAM_SIZE_MB):
    size = size_mb * 1024 * 1024
    src = bytearray(os.urandom(1024 * 1024))
    data = bytearray()
    while len(data) < size:
        data += src[:min(len(src), size - len(data))]
    t0 = time.perf_counter()
    copies = 0
    end = t0 + 3.0
    while time.perf_counter() < end:
        dst = bytearray(data)
        copies += 1
        del dst
    elapsed = time.perf_counter() - t0
    return {"mb_s": round((copies * size_mb) / elapsed, 1),
            "size_mb": size_mb, "copies": copies,
            "time_s": round(elapsed, 1)}


def disk_test(size_mb=DISK_SIZE_MB):
    tmpdir = tempfile.gettempdir()
    path = os.path.join(tmpdir, "pts_bench_test.bin")
    chunk = b"\x00" * (1024 * 1024)
    try:
        t0 = time.perf_counter()
        with open(path, "wb") as f:
            for _ in range(size_mb):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        write_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        with open(path, "rb") as f:
            while f.read(1024 * 1024):
                pass
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
        root.geometry("740x880")
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

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        top = tk.Frame(root, padx=12, pady=8)
        top.pack(fill="x")
        tk.Label(top, text=APP_NAME, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(top, text="CPU + RAM + Disk + GPU  |  Stress test až 4 h  |  v1.2.0",
                 font=("Segoe UI", 10), fg="#666").pack(anchor="w")

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

        # --- Stress test ---
        sf = tk.LabelFrame(root, text=" Stress test — záťaž PC ", padx=10, pady=6)
        sf.pack(fill="x", padx=12, pady=4)
        tk.Label(sf, text="Dĺžka:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.stress_dur = ttk.Combobox(sf, values=list(STRESS_DURATIONS.keys()),
                                       state="readonly", width=14)
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

        # --- Graf ---
        gf = tk.LabelFrame(root, text=" Graf — teplota a zaťaženie (živý, každé 2 s) ", padx=8, pady=4)
        gf.pack(fill="x", padx=12, pady=4)
        self.graph = tk.Canvas(gf, width=700, height=130, bg="white")
        self.graph.pack()
        self.live_label = tk.Label(gf, text="CPU: —  |  Teplota CPU: —  |  GPU: —",
                                   font=("Consolas", 9), fg="#333")
        self.live_label.pack(anchor="w")
        tk.Label(gf, text="zelená = zaťaženie CPU %   •   červená = teplota CPU °C   •   oranžová = teplota GPU °C   •   ak teplota nejde zistiť, graf ukazuje len zaťaženie",
                 font=("Segoe UI", 8), fg="#666").pack(anchor="w")

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", padx=12)
        self.status = tk.Label(root, text="Pripravený.", font=("Segoe UI", 10), fg="#333")
        self.status.pack(anchor="w", padx=12, pady=2)

        out = tk.Frame(root, padx=12, pady=4)
        out.pack(fill="both", expand=True)
        self.out = tk.Text(out, font=("Consolas", 10), bg="#111",
                           fg="#0f0", insertbackground="white", height=8)
        self.out.pack(fill="both", expand=True)
        self.log("PTS Benchmark v1.2.0 - pripraveny.\n"
                 "GPU test = 2D render test (nie 3DMark).\n"
                 "Stress: pri 90 °C+ zastav test, pri 95 °C sa zastavi sam.\n")
        # Monitor loop - bezi stale, aj bez stressu
        self.root.after(2000, self.monitor_tick)

    def show_info(self):
        self.info_text.delete("1.0", "end")
        for k, v in system_info().items():
            self.info_text.insert("end", f"{k}: {v}\n")
        self.info_text.config(state="disabled")

    def log(self, s):
        self.out.insert("end", s)
        self.out.see("end")
        self.root.update_idletasks()

    def set_status(self, s):
        self.status.config(text=s)
        self.root.update_idletasks()

    # ----- Monitor + graf -----
    def monitor_tick(self):
        try:
            cpu_load = get_cpu_load()
            if cpu_load is None:
                cpu_load = 100.0 if self.stress_running and self.var_cpu.get() else 0.0
            cpu_temp = get_cpu_temp()
            gpu = get_gpu_stats()
            gpu_temp = gpu["temp"] if gpu else None
            elapsed = time.time() - self.monitor_start
            self.history.append((elapsed, cpu_load, cpu_temp, gpu_temp))
            if len(self.history) > 300:  # max 10 min v grafe
                self.history.pop(0)
            gpu_txt = f"{gpu_temp:.0f} °C / {gpu['load']:.0f}%" if gpu else "—"
            temp_txt = f"{cpu_temp:.1f} °C" if cpu_temp is not None else "nedá sa zistiť"
            self.live_label.config(
                text=f"CPU: {cpu_load:.0f}%  |  Teplota CPU: {temp_txt}  |  GPU: {gpu_txt}")
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
        cv.delete("all")
        w, h = 700, 130
        if len(self.history) < 2:
            cv.create_text(w // 2, h // 2, text="Čakám na dáta...", fill="#888")
            return
        # mriezka 0 / 50 / 100
        for val, y in [(100, 8), (50, h // 2), (0, h - 8)]:
            cv.create_line(30, y, w - 5, y, fill="#eee")
            cv.create_text(15, y, text=str(val), font=("Consolas", 8), fill="#888")
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
                cv.create_line(a, b, fill=color, width=2)

        line(1, "green")       # CPU load %
        line(2, "red")         # CPU temp °C (0-100)
        line(3, "orange")      # GPU temp °C

    # ----- Rychle testy -----
    def _run_thread(self, fn, label):
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
            self.log("\n=== KONIEC ===\nCelkove PTS skore: "
                     f"{self.pts_score()}\n")
        self._run_thread(job, "Beží celý test (~25 s)")

    def run_cpu(self):
        self._run_thread(self.do_cpu, "CPU test")
    def run_ram(self):
        self._run_thread(self.do_ram, "RAM test")
    def run_disk(self):
        self._run_thread(self.do_disk, "Disk test")

    def do_cpu(self):
        self.log("\n[CPU] ...\n")
        r = cpu_test()
        self.results["cpu"] = r
        self.log(f"  Single-core: {r['single_kops']} kops/s\n"
                 f"  Multi-core ({r['cores']} jadier): {r['multi_kops']} kops/s\n")

    def do_ram(self):
        self.log("\n[RAM] ...\n")
        r = ram_test()
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
        win.geometry("640x380")
        cv = tk.Canvas(win, width=640, height=360, bg="black")
        cv.pack()
        colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "white"]
        frames = 0
        end = time.perf_counter() + 3.0
        while time.perf_counter() < end:
            cv.delete("all")
            for _ in range(60):
                x, y = random.randint(0, 600), random.randint(0, 320)
                c = random.choice(colors)
                cv.create_rectangle(x, y, x + 40, y + 40, fill=c, outline="")
                cv.create_oval(x, y, x + 25, y + 25, fill=c, outline="")
            win.update()
            frames += 1
        win.destroy()
        fps = round(frames / 3.0, 1)
        self.results["gpu"] = {"fps": fps, "gpu": gpu, "vram_gb": vram}
        self.log(f"  FPS (2D, 60 objektov/frame): {fps}\n"
                 f"  Pozn.: nie je to 3D test ako 3DMark.\n")

    # ----- Stress test -----
    def start_stress(self):
        if self.stress_running or self.running:
            messagebox.showwarning("Beží test", "Počkaj, kým dobehne aktuálny test.")
            return
        dur_name = self.stress_dur.get()
        self.stress_duration = STRESS_DURATIONS.get(dur_name, 3600)
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
        self.gpu_win.geometry("640x380")
        self.gpu_cv = tk.Canvas(self.gpu_win, width=640, height=360, bg="black")
        self.gpu_cv.pack()
        self.gpu_stress_frame()

    def gpu_stress_frame(self):
        if not self.stress_running or self.gpu_win is None:
            return
        try:
            cv = self.gpu_cv
            cv.delete("all")
            colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "white"]
            for _ in range(80):
                x, y = random.randint(0, 600), random.randint(0, 320)
                c = random.choice(colors)
                cv.create_rectangle(x, y, x + 40, y + 40, fill=c, outline="")
            self.gpu_win.update_idletasks()
        except Exception:
            pass
        self.root.after(50, self.gpu_stress_frame)

    def stress_worker(self):
        cores = os.cpu_count() or 1
        cycles = 0
        while self.stress_running:
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
