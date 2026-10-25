import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.retrieval import RetrievalIndex

CHECKS = [
    ("human oversight", "human_oversight"),
    ("bias testing", "bias"),
    ("system logs", "log"),
]


def main():
    path = ROOT / "app" / "data" / "frameworks.json"
    frameworks = json.loads(path.read_text(encoding="utf-8"))
    index = RetrievalIndex(frameworks)
    passed = 0
    for query, expected in CHECKS:
        results = index.search(query, top_k=3)
        top = results[0]
        haystack = (top["control_type"] + " " + top["obligation"]).lower()
        ok = expected in haystack
        print("PASS" if ok else "FAIL", ": query=", repr(query), "top_control=", repr(top["control_type"]))
        if ok:
            passed += 1
    print(f"Retrieval eval: {passed}/{len(CHECKS)} passed")
    if passed < 2:
        print("Eval gate FAILED: need at least 2/3")
        raise SystemExit(1)
    print("Eval gate PASSED")


if __name__ == "__main__":
    main()
