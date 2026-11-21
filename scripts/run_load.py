#!/usr/bin/env python3
"""Run the actual JMX, preserve JTL evidence and stop only the server started here."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--java-home", default=os.environ.get("JAVA_HOME"))
parser.add_argument("--jmeter", required=True, help="Path to bin/ApacheJMeter.jar")
parser.add_argument("--output", default="results")
args = parser.parse_args()
if not args.java_home:
    parser.error("Specify --java-home (JDK 17+)")
JDK = Path(args.java_home).resolve() / "bin"
JMETER = Path(args.jmeter).resolve()
OUTPUT = (ROOT / args.output).resolve()
if (OUTPUT / "baseline").exists():
    parser.error("Existing results: use a fresh --output directory")
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8084"


def request(path, method="GET"):
    with urllib.request.urlopen(urllib.request.Request(BASE + path, method=method), timeout=5) as response:
        data = response.read()
        return json.loads(data) if data else None


def clean_up():
    count = 0
    while True:
        items = request("/api/tasks?q=load-&limit=100")["items"]
        if not items:
            return count
        for item in items:
            request("/api/tasks/" + str(item["id"]), "DELETE")
            count += 1


def monitor(stop, samples, names):
    while not stop.is_set():
        row = {"timestamp": time.time(), "metrics": {}}
        for name in names:
            try:
                query = "?tag=area:heap" if name == "jvm.memory.used" else ""
                row["metrics"][name] = request("/actuator/metrics/" + name + query)["measurements"]
            except Exception as error:
                row.setdefault("errors", []).append(str(error))
        samples.append(row)
        stop.wait(2)


def run_phase(name, users, duration, ramp, data=None):
    folder = OUTPUT / name
    folder.mkdir()
    samples, stop = [], threading.Event()
    watcher = threading.Thread(target=monitor, args=(stop, samples, metric_names), daemon=True)
    watcher.start()
    started = time.time()
    command = [str(JDK / "java"), "-Xms256m", "-Xmx512m", "-Djava.awt.headless=true", "-jar", str(JMETER),
               "-n", "-t", str(ROOT / "load/task-lifecycle.jmx"), "-l", str(folder / "requests.jtl"),
               "-j", str(folder / "jmeter.log"), f"-Jusers={users}", f"-Jduration={duration}", f"-Jramp={ramp}",
               "-Jdata=" + str(data or ROOT / "load/users.csv"),
               "-Jjmeter.save.saveservice.assertion_results_failure_message=true",
               "-Jjmeter.reportgenerator.overall_granularity=5000", "-e", "-o", str(folder / "dashboard")]
    try:
        with (folder / "console.txt").open("w") as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=duration+90)
    finally:
        stop.set()
        watcher.join(timeout=35)
    (folder / "monitor.json").write_text(json.dumps(samples, indent=2) + "\n")
    with (folder / "requests.jtl").open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows, f"{name}: no requests recorded"
    failures = sum(row["success"] != "true" for row in rows)
    cleanup = clean_up()
    phase = dict(name=name, users=users, duration_seconds=duration, ramp_seconds=ramp,
                 process_started_at=started, requests=len(rows), errors=failures,
                 cleanup_requests=cleanup, metric_samples=len(samples))
    (folder / "phase.json").write_text(json.dumps(phase, indent=2) + "\n")
    print(json.dumps(phase), flush=True)
    return phase


try:
    request("/actuator/health")
except Exception:
    pass
else:
    raise RuntimeError("Port 8084 already has a service; stop it before starting this isolated lab")

app_log = (OUTPUT / "application.log").open("w")
app = subprocess.Popen([str(JDK / "java"), "-Xms256m", "-Xmx512m", "-jar",
                        str(ROOT / "target/jmeter-api-lab-1.0.0.jar")],
                       cwd=ROOT, stdout=app_log, stderr=subprocess.STDOUT)
try:
    for attempt in range(80):
        if app.poll() is not None:
            raise RuntimeError("Application stopped during startup; inspect application.log")
        try:
            if request("/actuator/health")["status"] == "UP":
                break
        except Exception:
            time.sleep(.5)
    else:
        raise RuntimeError("Application did not become healthy")
    available = request("/actuator/metrics")["names"]
    metric_names = [name for name in ("process.cpu.usage", "jvm.memory.used", "jvm.threads.live",
                   "hikaricp.connections.active", "hikaricp.connections.pending") if name in available]
    negative_data = OUTPUT / "invalid-users.csv"
    negative_data.write_text("category,priority,minPriority,filterStatus\nreport,0,1,OPEN\n")
    negative = run_phase("validation-check", 1, 5, 1, negative_data)
    assert negative["errors"] == 1, "Invalid priority must be rejected and detected by the JMX assertion"
    warmup = run_phase("warmup", 10, 20, 5)
    assert warmup["errors"] == 0, "Warmup assertions failed"
    phases = []
    for name, users in (("baseline", 10), ("medium", 50), ("peak", 150), ("recovery", 10)):
        if name == "peak":
            recording = str(OUTPUT / "peak.jfr")
            # jcmd tokenizes diagnostic arguments, so paths with spaces require embedded quotes.
            result = subprocess.run([str(JDK / "jcmd"), str(app.pid), "JFR.start", "name=peak",
                                     "settings=profile", "duration=55s", f'filename="{recording}"'],
                                    capture_output=True, text=True, check=True)
            (OUTPUT / "jfr-start.txt").write_text(result.stdout + result.stderr)
        phases.append(run_phase(name, users, 45, 10))
        time.sleep(3)
    request("/actuator/health")
    # The database must return to its original 200 seeded tasks after cleanup.
    seed_count = sum(len(request(f"/api/tasks?limit=100&offset={offset}")["items"]) for offset in (0,100,200))
    assert seed_count == 200, f"Unexpected remaining records: {seed_count}"
    summary = {"date": time.strftime("%Y-%m-%d"), "phases": phases, "seed_count_after": seed_count,
               "metric_names": metric_names, "application_heap": "256m..512m", "jmeter_heap": "256m..512m"}
    (OUTPUT / "run.json").write_text(json.dumps(summary, indent=2) + "\n")
    assert all(phase["errors"] == 0 for phase in phases), "Load assertions failed; preserve and inspect results"
finally:
    if app.poll() is None:
        app.terminate()
        app.wait(timeout=30)
    app_log.close()
print("All four load phases passed; server stopped cleanly", flush=True)
