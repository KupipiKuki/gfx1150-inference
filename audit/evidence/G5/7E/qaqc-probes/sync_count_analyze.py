#!/usr/bin/env python3
"""Analyze a rocprofv3 --hip-trace rocpd database: cluster the
hipStreamSynchronize region records by >50ms gaps and print the per-cluster
counts (cold call vs warm calls). Usage:
    rocprofv3 --hip-trace -o /tmp/rocprof_out/p7e -- python3 sync_count_probe.py
    python3 sync_count_analyze.py /tmp/rocprof_out/p7e_results.db
"""
import sys
import sqlite3

db = sys.argv[1]
con = sqlite3.connect(db)
cur = con.cursor()
region = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rocpd_region_%'"
)][0]
strings = region.replace("region", "string")
rows = cur.execute(f"""
    SELECT r.start, r.end FROM {region} r JOIN {strings} s ON r.name_id = s.id
    WHERE s.string = 'hipStreamSynchronize' ORDER BY r.start
""").fetchall()
clusters = []
if rows:
    clusters = [[rows[0]]]
    for a, b in rows[1:]:
        if a - clusters[-1][-1][1] > 50_000_000:
            clusters.append([])
        clusters[-1].append((a, b))
print(f"total hipStreamSynchronize records: {len(rows)}")
print("syncs per call cluster (index 0 = cold; rest warm):", [len(c) for c in clusters])
