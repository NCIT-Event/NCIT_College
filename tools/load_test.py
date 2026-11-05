#!/usr/bin/env python3
"""Load test for the public website (standard library only).

    python3 tools/load_test.py http://localhost:8080 --users 10,50,100 --seconds 30

Each simulated visitor loops through a realistic mix of page views: the home
page and its data, department pages, news, notices, events, clubs, admissions,
static files, and searches (half of them with fresh words, so they miss the
cache and reach the search service and database). Reports requests per
second, response times (median, 95th and 99th percentile) and errors for each
level of concurrent visitors.

Run it against staging, or production outside working hours: it is meant to
be heavy.
"""

import argparse
import http.client
import random
import statistics
import threading
import time
from urllib.parse import urlsplit

MIX = [  # (weight, path)
    (10, "/"), (10, "/api/v1/content/public/home"), (4, "/api/v1/academics/public/departments"),
    (6, "/assets/css/site.css"), (6, "/assets/js/site.js"),
    (6, "/departments/computer"), (6, "/api/v1/academics/public/departments/computer"),
    (4, "/api/v1/content/public/news"), (4, "/api/v1/content/public/notices"), (3, "/api/v1/events/public/events"),
    (2, "/api/v1/events/public/calendar"), (2, "/api/v1/eca/public/clubs"), (3, "/api/v1/admissions/public/intakes"),
    (2, "/api/v1/careers/public/jobs"), (2, "/api/v1/alumni/public/featured"), (3, "/search?q=computer"),
    (4, "SEARCH_CACHED"), (4, "SEARCH_FRESH"),
]
WORDS = ["computer", "civil", "robot", "exam", "notice", "fest", "club", "admission", "lecturer", "music", "sports", "result",
         "software", "network", "seminar", "workshop", "photography", "architecture", "management", "alumni"]


def pick():
    path = random.choices([p for _, p in MIX], weights=[w for w, _ in MIX])[0]
    if path == "SEARCH_CACHED":
        return "/api/v1/search/public/search?q=" + random.choice(WORDS[:5])
    if path == "SEARCH_FRESH":  # unique query string: always a cache miss
        return f"/api/v1/search/public/search?q={random.choice(WORDS)}&n={random.random()}"
    return path


def visitor(base, stop, samples, errors, lock):
    url = urlsplit(base)
    conn = None
    while not stop.is_set():
        path = pick()
        t0 = time.perf_counter()
        try:
            if conn is None:
                conn = (http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection)(url.netloc, timeout=15)
            conn.request("GET", path, headers={"User-Agent": "ncit-load-test", "Accept-Encoding": "gzip"})
            res = conn.getresponse()
            res.read()
            ok = res.status < 500 and res.status != 429
            if res.getheader("connection", "").lower() == "close":
                conn.close()
                conn = None
        except (OSError, http.client.HTTPException):
            ok = False
            conn = None
        took = (time.perf_counter() - t0) * 1000
        with lock:
            samples.append(took)
            if not ok:
                errors.append(path)


def run(base, users, seconds):
    stop, lock, samples, errors = threading.Event(), threading.Lock(), [], []
    threads = [threading.Thread(target=visitor, args=(base, stop, samples, errors, lock), daemon=True) for _ in range(users)]
    for t in threads:
        t.start()
    time.sleep(seconds)
    stop.set()
    for t in threads:
        t.join(timeout=20)
    q = statistics.quantiles(samples, n=100) if len(samples) > 100 else [0] * 99
    return {"users": users, "requests": len(samples), "rps": len(samples) / seconds, "p50": q[49], "p95": q[94], "p99": q[98],
            "errors": len(errors), "error_rate": len(errors) / max(len(samples), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://localhost:8080")
    ap.add_argument("--users", default="10,50,100")
    ap.add_argument("--seconds", type=int, default=30)
    a = ap.parse_args()
    print(f"Load test against {a.base}, {a.seconds} s per level\n")
    print(f"{'visitors':>9} {'requests':>9} {'req/s':>8} {'median':>9} {'p95':>9} {'p99':>9} {'errors':>8}")
    for users in [int(u) for u in a.users.split(",")]:
        r = run(a.base.rstrip("/"), users, a.seconds)
        print(f"{r['users']:>9} {r['requests']:>9} {r['rps']:>8.0f} {r['p50']:>7.0f}ms {r['p95']:>7.0f}ms {r['p99']:>7.0f}ms "
              f"{r['errors']:>4} ({r['error_rate']:.1%})")


if __name__ == "__main__":
    main()
