"""Session, turn and audit storage. DynamoDB in AWS (single table, pk/sk), in-memory for local dev.
Only text is stored: audio is never kept."""
import json
import os
import random
import string
import threading
import time
import uuid


def now_ms():
    return int(time.time() * 1000)


class MemoryStore:
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    def _put(self, pk, sk, data):
        with self.lock:
            self.items[(pk, sk)] = json.dumps(data)

    def _get(self, pk, sk):
        raw = self.items.get((pk, sk))
        return json.loads(raw) if raw else None

    def _query(self, pk, sk_after):
        with self.lock:
            rows = [(sk, v) for (p, sk), v in self.items.items() if p == pk and sk > sk_after and sk.startswith("T#")]
        return [json.loads(v) for sk, v in sorted(rows)]

    def _scan_sessions(self):
        return [json.loads(v) for (p, sk), v in self.items.items() if sk == "META" and p.startswith("S#")]

    # Shared API ----------------------------------------------------------------------------------
    def create_session(self, meta):
        code = self._free_code()
        sid = uuid.uuid4().hex[:12]
        meta = {**meta, "id": sid, "code": code, "createdAt": now_ms(), "updatedAt": now_ms(), "status": "active"}
        self._put(f"S#{sid}", "META", meta)
        self._put(f"C#{code}", "META", {"sessionId": sid})
        return meta

    def _free_code(self):
        for _ in range(50):
            code = "".join(random.choices(string.digits, k=4))
            ref = self._get(f"C#{code}", "META")
            if not ref:
                return code
            s = self.get_session(ref["sessionId"])
            if not s or s.get("status") == "ended":
                return code
        return "".join(random.choices(string.digits, k=6))

    def get_session(self, sid):
        return self._get(f"S#{sid}", "META")

    def find_by_code(self, code):
        ref = self._get(f"C#{code}", "META")
        return self.get_session(ref["sessionId"]) if ref else None

    def update_session(self, sid, **fields):
        meta = self.get_session(sid)
        if not meta:
            return None
        meta.update(fields)
        meta["updatedAt"] = now_ms()
        self._put(f"S#{sid}", "META", meta)
        return meta

    def add_turn(self, sid, turn):
        ts = now_ms()
        turn = {**turn, "id": f"{ts}-{uuid.uuid4().hex[:6]}", "ts": ts}
        self._put(f"S#{sid}", f"T#{turn['id']}", turn)
        self.update_session(sid, lastTurnAt=ts)
        return turn

    def list_turns(self, sid, since=0):
        return self._query(f"S#{sid}", f"T#{since:013d}-~" if since else "T#")

    def list_sessions(self):
        return sorted(self._scan_sessions(), key=lambda s: -s["createdAt"])


class DynamoStore(MemoryStore):
    def __init__(self, table):
        import boto3
        self.t = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")).Table(table)

    def _put(self, pk, sk, data):
        self.t.put_item(Item={"pk": pk, "sk": sk, "data": json.dumps(data, ensure_ascii=False)})

    def _get(self, pk, sk):
        item = self.t.get_item(Key={"pk": pk, "sk": sk}, ConsistentRead=True).get("Item")
        return json.loads(item["data"]) if item else None

    def _query(self, pk, sk_after):
        from boto3.dynamodb.conditions import Key
        out, kwargs = [], {"KeyConditionExpression": Key("pk").eq(pk) & Key("sk").between(sk_after, "T#~"),
                           "ConsistentRead": True}
        while True:
            resp = self.t.query(**kwargs)
            out += [json.loads(i["data"]) for i in resp["Items"] if i["sk"] > sk_after]
            if "LastEvaluatedKey" not in resp:
                return out
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def _scan_sessions(self):
        from boto3.dynamodb.conditions import Attr
        out, kwargs = [], {"FilterExpression": Attr("sk").eq("META") & Attr("pk").begins_with("S#")}
        while True:
            resp = self.t.scan(**kwargs)
            out += [json.loads(i["data"]) for i in resp["Items"]]
            if "LastEvaluatedKey" not in resp:
                return out
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def load_store():
    table = os.environ.get("CB_TABLE")
    return DynamoStore(table) if table else MemoryStore()
