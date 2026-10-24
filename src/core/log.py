import json
import time


def log(level, event, **fields):
    """One JSON line per event; CloudWatch Logs Insights queries in infra/monitoring.tf rely on these names."""
    print(json.dumps({"level": level, "event": event, "t": round(time.time(), 3), **fields}, default=str))
