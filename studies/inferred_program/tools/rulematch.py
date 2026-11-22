"""Recover a learned rule's supporting examples outside the engine (X4), by matching the rule's text against facts.

A rule as the engine prints it:
    TREE [? is output of ?](a,g) & [? has kind ?](g,step) & [? has first input ?](g,y1) & [? has value ?](y1,s1) => [? has value ?](a,s2)
    [? at ?](a,b) & [? next ?](b,c) => [? then ?](a,c)
Variables are a-h and y<n>; anything else is a constant. support(rule, facts) returns (n, k, examples): n body
matches, k of them with the conclusion stated too, and the head facts of those k (the examples behind the rule).
"""
import collections, re

ATOM = re.compile(r"\[\? (.*?) \?\]\(([^,()]+),([^,()]+)\)")
VAR = re.compile(r"^(?:[a-h]|y\d+)$")


def parse(text):
    body, head = text.replace("TREE ", "").split("=>")
    b = [(r, x, y) for r, x, y in ATOM.findall(body)]
    h = ATOM.findall(head)[0]
    return b, h


def index(facts):
    """facts: iterable of (relation, subject, object)."""
    fwd = collections.defaultdict(lambda: collections.defaultdict(set)); rev = collections.defaultdict(lambda: collections.defaultdict(set))
    have = set()
    for r, s, o in facts:
        fwd[r][s].add(o); rev[r][o].add(s); have.add((r, s, o))
    return fwd, rev, have


def matches(body, idx, distinct=True):
    fwd, rev, _ = idx
    def go(i, env):
        if i == len(body): yield dict(env); return
        r, x, y = body[i]
        xv, yv = env.get(x, None if VAR.match(x) else x), env.get(y, None if VAR.match(y) else y)
        if xv is not None and yv is not None:
            if yv in fwd[r].get(xv, ()): yield from go(i + 1, env)
        elif xv is not None:
            for o in fwd[r].get(xv, ()):
                if distinct and o in env.values(): continue
                env[y] = o; yield from go(i + 1, env); del env[y]
        elif yv is not None:
            for s in rev[r].get(yv, ()):
                if distinct and s in env.values(): continue
                env[x] = s; yield from go(i + 1, env); del env[x]
        else:
            for s, os in list(fwd[r].items()):
                for o in os:
                    if distinct and (s in env.values() or o in env.values() or s == o): continue
                    env[x], env[y] = s, o; yield from go(i + 1, env); del env[x], env[y]
    # start from the atom that binds the head subject, so the search is anchored
    yield from go(0, {})


def support(text, idx):
    body, (hr, hx, hy) = parse(text)
    _, _, have = idx
    n = k = 0; ex = []
    for env in matches(body, idx):
        n += 1
        s, o = env.get(hx, hx), env.get(hy, hy)
        if (hr, s, o) in have: k += 1; ex.append(f"{s} {hr} {o}")
    return n, k, ex
