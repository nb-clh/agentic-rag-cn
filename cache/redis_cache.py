import json
import time


class RedisCache:
    def __init__(self, redis_client, ttl=3600):
        self.redis = redis_client
        self.ttl = ttl

    def get(self, key: str):
        try:
            data = self.redis.get(f"cache:{key}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    def set(self, key: str, value, ttl=None):
        try:
            self.redis.setex(
                f"cache:{key}",
                ttl or self.ttl,
                json.dumps(value, ensure_ascii=False)
            )
        except Exception:
            pass

    def delete(self, key: str):
        try:
            self.redis.delete(f"cache:{key}")
        except Exception:
            pass
