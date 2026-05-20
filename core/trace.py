import time
import uuid


class Trace:
    def __init__(self, query: str = "", metadata: dict = None):
        self.trace_id = str(uuid.uuid4())
        self.query = query
        self.metadata = metadata or {}
        self.events = []
        self.start_time = time.time()

    def log(self, step: str, data=None):
        self.events.append({
            "step": step,
            "data": str(data)[:500] if data else None,
            "ts": time.time()
        })

    def finalize(self, final_output, score: float = 0.0):
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "latency": time.time() - self.start_time,
            "events": self.events,
            "final": final_output,
            "score": score,
            "metadata": self.metadata
        }
