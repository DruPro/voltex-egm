"""Data-derived shard assignments (studies/shard_general). Both read fact lines only (no answer key).

auto(lines, n)    restreamed linear deterministic greedy partitioning (LDG, Stanton & Kliot 2012; restreaming,
                  Nishimura & Ugander 2013) over the graph of all facts, then a reference rule. No relation names.
                  1. Graph: one node per entity (first and last word of a fact); edge weight = number of facts
                     linking the two entities, any relation, either direction.
                  2. Order: connected components, largest first (ties: smallest name), each in breadth-first order
                     from its smallest name, neighbours in name order.
                  3. Pass 1: place each node in the shard maximising w(node, shard) * (1 - load/C), with
                     C = SLACK * nodes / n; ties go to the least-loaded, then lowest-numbered shard.
                     Passes 2..PASSES: the same, with w() counted against the previous pass's assignment.
                  4. Reference rule: a node keeps its shard only if at least MAJORITY of its link weight goes to
                     nodes in that shard; otherwise it is left unassigned, so egm.shard treats its facts as
                     reference facts (routed to every shard that mentions it).
                  5. Orphan repair: an unassigned node with no assigned neighbour goes back to its shard.
random(lines, n)  each entity to shard sha1(name) mod n. No reference rule (the naive control).

Constants were fixed before any confirmatory run (PREREGISTRATION.md): SLACK 1.05, PASSES 3, MAJORITY 0.5.
"""
import collections, hashlib

SLACK, PASSES, MAJORITY = 1.05, 3, 0.5


def _graph(lines):
    adj = collections.defaultdict(lambda: collections.defaultdict(int))
    for l in lines:
        w = l.split()
        if len(w) < 3 or w[0] == w[-1]: continue
        adj[w[0]][w[-1]] += 1; adj[w[-1]][w[0]] += 1
    return adj


def _order(adj):
    seen, comps = set(), []
    for v in sorted(adj):
        if v in seen: continue
        comp, q = [], collections.deque([v]); seen.add(v)
        while q:
            x = q.popleft(); comp.append(x)
            for y in sorted(adj[x]):
                if y not in seen: seen.add(y); q.append(y)
        comps.append(comp)
    comps.sort(key=lambda c: (-len(c), min(c)))
    return [v for c in comps for v in c]


def auto(lines, n):
    adj = _graph(lines)
    order = _order(adj)
    cap = SLACK * len(order) / n
    prev = {}
    for p in range(PASSES):
        cur, load = {}, [0] * n
        ref = cur if p == 0 else prev
        for v in order:
            w = [0.0] * n
            for y, c in adj[v].items():
                s = ref.get(y)
                if s is not None: w[s] += c
            best = max(range(n), key=lambda i: (w[i] * (1 - load[i] / cap), -load[i], -i))
            if w[best] * (1 - load[best] / cap) <= 0: best = min(range(n), key=lambda i: (load[i], i))
            cur[v] = best; load[best] += 1
        prev = cur
    out = {}
    for v, s in prev.items():
        tot = sum(adj[v].values()); inside = sum(c for y, c in adj[v].items() if prev.get(y) == s)
        if tot == 0 or inside / tot >= MAJORITY: out[v] = s
    # 5. Orphan repair (added after the pilot, see PREREGISTRATION.md): an unassigned entity that no assigned
    #    entity links to would have its facts reach no shard, so it goes back to its pass-3 shard. One pass.
    back = {v: prev[v] for v in prev if v not in out and not any(y in out for y in adj[v])}
    out.update(back)
    return out


def random(lines, n):
    ents = {x for l in lines for x in (l.split()[0], l.split()[-1]) if len(l.split()) >= 3}
    return {e: int(hashlib.sha1(e.encode()).hexdigest(), 16) % n for e in ents}
