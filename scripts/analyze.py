#!/usr/bin/env python3
"""Analyze original JTL; all steady-state rates use the same 25-second window."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--results", default="results")
args = parser.parse_args()
results = ROOT / args.results


def stats(rows, seconds):
    values = sorted(int(row["elapsed"]) for row in rows)
    def percentile(p):
        return values[max(0, math.ceil(len(values)*p)-1)] if values else None
    return dict(count=len(rows), errors=sum(row["success"] != "true" for row in rows),
                rps=len(rows)/seconds, mean_ms=statistics.mean(values) if values else None,
                p50_ms=percentile(.5), p95_ms=percentile(.95), p99_ms=percentile(.99),
                max_ms=max(values) if values else None)


summary = []
flat = []
for phase in json.loads((results / "run.json").read_text())["phases"]:
    folder = results / phase["name"]
    with (folder / "requests.jtl").open() as f:
        rows = list(csv.DictReader(f))
    start = min(int(row["timeStamp"]) for row in rows)
    end = max(int(row["timeStamp"])+int(row["elapsed"]) for row in rows)
    lower, upper = start + 15000, start + 40000
    steady = [row for row in rows if lower <= int(row["timeStamp"])+int(row["elapsed"]) < upper]
    labels = sorted({row["label"] for row in rows})
    assert len(labels) == 6, "All six operations must be measured"
    details = {label: stats([row for row in steady if row["label"] == label], 25) for label in labels}
    assert all(item["count"] > 0 for item in details.values())
    for label, item in details.items():
        flat.append(dict(phase=phase["name"], users=phase["users"], endpoint=label, **item))
    metrics = json.loads((folder / "monitor.json").read_text())
    sampled = [sample for sample in metrics if lower/1000 <= sample["timestamp"] < upper/1000]
    maxima = {}
    for sample in sampled:
        for name, measurements in sample["metrics"].items():
            value = next((m["value"] for m in measurements if m["statistic"] == "VALUE"), None)
            if value is not None:
                maxima[name] = max(maxima.get(name, value), value)
    summary.append(dict(name=phase["name"], users=phase["users"], started_at_ms=start,
                        ended_at_ms=end, steady_from_ms=lower, steady_to_ms=upper,
                        whole_run=stats(rows, (end-start)/1000), steady=stats(steady, 25),
                        endpoints=details, sampled_metric_maxima=maxima,
                        monitoring_errors=sum(len(m.get("errors", [])) for m in metrics),
                        cleanup_requests=phase["cleanup_requests"]))
(results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
with (results / "endpoints.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(flat[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(flat)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(11,4), layout="constrained")
names = [str(p["users"]) + (" (возврат)" if p["name"] == "recovery" else "") for p in summary]
x = list(range(len(summary)))
axes[0].bar(x, [p["steady"]["rps"] for p in summary], color="#286b9c")
axes[0].set_ylabel("Завершённых HTTP-запросов/с")
axes[0].set_title("Пропускная способность")
axes[1].plot(x, [p["steady"]["p95_ms"] for p in summary], marker="o", label="p95")
axes[1].plot(x, [p["steady"]["p99_ms"] for p in summary], marker="o", label="p99")
axes[1].set_ylabel("Время отклика, мс")
axes[1].set_title("Задержки в окне 15–40 секунд")
axes[1].legend()
for axis in axes:
    axis.set_xticks(x, names)
    axis.set_xlabel("Одновременных пользователей")
    axis.grid(axis="y", alpha=.2)
(ROOT / "report/images").mkdir(exist_ok=True, parents=True)
fig.savefig(ROOT / "report/images/load-comparison.png", dpi=170)
print(json.dumps([{k:v for k,v in p.items() if k in ("name","users","steady","sampled_metric_maxima","monitoring_errors")}
                  for p in summary], indent=2))
