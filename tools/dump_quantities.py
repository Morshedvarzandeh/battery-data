#!/usr/bin/env python3
"""Dump bd.quantity to json-schema/quantity-registry.json for offline CI."""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db = sys.argv[1] if len(sys.argv) > 1 else "batterydb"
sql = "SELECT json_object_agg(code, required_conditions) FROM bd.quantity;"
out = subprocess.run(["psql", "-tAq", "-d", db, "-c", sql],
                     capture_output=True, text=True, check=True).stdout.strip()
path = os.path.join(ROOT, "json-schema", "quantity-registry.json")
json.dump(json.loads(out), open(path, "w"), indent=1, sort_keys=True)
print(f"wrote {path} ({len(json.loads(out))} quantities)")
