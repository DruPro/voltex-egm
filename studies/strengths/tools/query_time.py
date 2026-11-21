"""Time the three phases on the replication data (round 3 `full` settings): ingest (egm.open), learning and inference
(the first question triggers it), and questions afterwards.  python3 query_time.py  ->  ../results_dist/query_time.json"""
import json, os, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT)
import egm  # noqa: E402
ST = {"MAXWORDS": 72600, "TENDENCYSTEPS": 0, "TREES": 1, "CHAIN": 3, "DEPTH": 0}
Q = ["pip___internal__cli__base_command__Command is a subclass of ?", "? is a subclass of logging__Handler",
     "attr___make__Attribute____init__ belongs to package ?", "PIL__Image__Image__resize__a0 is bound to ?"]
t0 = time.time(); e = egm.open(os.path.join(STUDY, "obs_dist", "facts.txt"), settings=ST, binary=os.path.join(ROOT, "build", "voltex2"))
t1 = time.time(); e.ask(Q[0]); t2 = time.time()
ts = []
for q in Q * 25:
    a = time.time(); e.ask(q); ts.append(time.time() - a)
e.close()
out = {"settings": ST, "ingest_s": round(t1 - t0, 2), "first_question_s": round(t2 - t1, 1), "questions": len(ts),
       "query_ms_median": round(statistics.median(ts) * 1000, 2), "query_ms_max": round(max(ts) * 1000, 2)}
json.dump(out, open(os.path.join(STUDY, "results_dist", "query_time.json"), "w"), indent=1); print(out)
