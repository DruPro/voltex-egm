"""The harness: memory and a clock around the engine. It never decides a transition.

Each step: create a step entity for the current (state, symbol) with three open output slots, ingest it, ask the
engine for each slot's value, and apply the answer to the tape it holds. If any slot has no answer or more than one,
stop and report unknown. The engine's answers are never stated back as facts.
"""
import time
import tm


def rule_set(e, about=None):
    """Accepted rules as (text, tier). about="value": rules concluding a wire's value; about="step": rules concluding a
    step output slot (anchored at the slot: `is write|move|next of ?](a,`)."""
    rs = [(r.text, r.tier) for r in e.rules()]
    if about == "value": rs = [x for x in rs if "=> [? has value ?]" in x[0]]
    if about == "step": rs = [x for x in rs if any(f"[? is {k} of ?](a," in x[0] for k in ("write", "move", "next"))]
    return sorted(rs)


def run_machine(e, prog, tape, head, names, max_steps=500, strict=True):
    state, blank = tm.START[prog], tm.BLANK[prog]
    tape = dict(tape); trace = []; t0 = time.time()
    while state != "halt" and len(trace) < max_steps:
        sym = tape.get(head, blank)
        lines, slots = tm.step_facts(names, state, sym)
        e.ingest_many(lines)
        got = {k: e.values(f"{w} {tm.REL[k]} ?", strict=strict) for k, w in slots.items()}
        if any(len(v) != 1 for v in got.values()):
            return {"status": "unknown", "at_step": len(trace), "state": state, "symbol": sym,
                    "answers": got, "steps": len(trace), "seconds": round(time.time() - t0, 3)}
        w, m, n = got["write"][0], got["move"][0], got["next"][0]
        trace.append((state, sym, w, m, n))
        tape[head] = w; head += 1 if m == "right" else -1; state = n
    return {"status": "halted" if state == "halt" else "step limit", "steps": len(trace), "tape": tape, "head": head,
            "seconds": round(time.time() - t0, 3), "trace": trace}
