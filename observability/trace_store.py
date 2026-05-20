import time
import json
import os


class TraceStore:
    def __init__(self, redis_client, trace_dir="traces"):
        self.redis = redis_client
        self.trace_dir = trace_dir
        os.makedirs(trace_dir, exist_ok=True)

    def save(self, trace: dict):
        trace_id = trace.get("trace_id", trace.get("id", "unknown"))
        trace["saved_at"] = time.time()
        # Redis
        try:
            self.redis.setex(f"trace:{trace_id}", 86400, json.dumps(trace, default=str))
        except Exception:
            pass
        # File backup
        try:
            path = os.path.join(self.trace_dir, f"{trace_id}.json")
            with open(path, "w") as f:
                json.dump(trace, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass

    def get(self, trace_id: str):
        try:
            data = self.redis.get(f"trace:{trace_id}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        try:
            path = os.path.join(self.trace_dir, f"{trace_id}.json")
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        except Exception:
            pass
        return None
