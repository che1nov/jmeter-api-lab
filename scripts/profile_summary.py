#!/usr/bin/env python3
"""Summarize JFR without claiming that a few sampled stacks prove a bottleneck."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--java-home", required=True)
parser.add_argument("--results", default="results")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
folder = root / args.results
jfr = Path(args.java_home) / "bin/jfr"
recording = folder / "peak.jfr"
summary = subprocess.run([str(jfr), "summary", str(recording)], capture_output=True, text=True, check=True)
(folder / "jfr-summary.txt").write_text(summary.stdout)
export = subprocess.run([str(jfr), "print", "--json", "--events", "jdk.ExecutionSample,jdk.GarbageCollection",
                         "--stack-depth", "12", str(recording)], capture_output=True, check=True)
with gzip.open(folder / "jfr-events.json.gz", "wb") as output:
    output.write(export.stdout)
events = json.loads(export.stdout)["recording"]["events"]
methods = Counter()
gc = []
samples = 0
for event in events:
    if event["type"] == "jdk.ExecutionSample":
        samples += 1
        frames = (event["values"].get("stackTrace") or {}).get("frames", [])
        if frames:
            method = frames[0]["method"]
            methods[method["type"]["name"].replace("/", ".") + "." + method["name"]] += 1
    else:
        gc.append(event["values"])
result = dict(scope="Full 55-second JFR recording started immediately before peak JMeter launch",
              execution_samples=samples, top_leaf_methods=methods.most_common(10), garbage_collections=gc,
              gc_pause_sum_ms=sum(float(e["sumOfPauses"][2:-1])*1000 for e in gc),
              gc_pause_max_ms=max((float(e["longestPause"][2:-1])*1000 for e in gc), default=0))
(folder / "jfr-analysis.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
