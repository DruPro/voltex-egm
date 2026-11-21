// Voltex v2.2 (EGM): v2.1 + source-aware evidence layer (OBSERVE envelope, projection, history, neutral flags).
// The reasoning substrate (relations, rule mining, inference) is v2.1's, unchanged.
// ============================================================================
//  VOLTEX v2.1  —  counted grammar memory with an inference layer
//
//  v2.1 adds five changes, each adopted only after a controlled experiment
//  (see "Voltex Improvement Experiments: Findings and Decisions"):
//   1. Coverage-aware rule acceptance (lower-only): when the data looks sparse,
//      the rate bar is relaxed to 0.8 x estimated completeness; never raised.
//   2. Confidence labels: every rule and derived fact is "law" (estimated
//      reliability >= 0.95) or "tendency".
//   3. Contradictions need two distinct rules agreeing on the alternative.
//   4. RETRACT and UPDATE: facts can be removed or replaced exactly.
//   5. Staleness check: after an UPDATE, the changed subject (and what points
//      at it) is re-checked by law-tier rules and kept out of rule evidence.
//  SET COVERAGE|LABELS|CORROBORATE|STALE 0 turns each off; all four off
//  reproduces v2.0 output exactly.
//
//  What changed from voltex_paged.cpp, and why:
//   * No SHA-256. Identity is a map lookup: a word maps to an integer id, a
//     repeated pair of symbols maps to a rule id. Same structure → same id,
//     found in one lookup instead of hashing 64-byte buffers at every level.
//   * No vitality / weights. The only stored numbers are counts of what was
//     ingested. Every probability is computed from counts at query time.
//   * Training is ingesting. INGEST appends tokens to an online grammar
//     (Sequitur: every pair seen twice anywhere becomes a shared rule) and
//     bumps counts. Nothing else is fitted. Categories, templates and
//     inference rules are derived on demand from those counts.
//   * Inference layer: category discovery, next-token prediction with
//     generalisation through categories, fill-in-the-blank queries, relation
//     templates, rule discovery (inverse / transitive / composition) scored
//     by evidence, and deduction with explanations.
//
//  Build:  g++ -std=c++17 -O2 voltex2.cpp -o voltex2
//          (-DVTX_ORDERED_MAPS swaps every unordered_map for std::map)
// ============================================================================
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
#ifndef _WIN32
#include <unistd.h>
#endif

using u32 = uint32_t;
using u64 = uint64_t;

#ifdef VTX_ORDERED_MAPS
template <class K, class V> using Map = std::map<K, V>;
#else
template <class K, class V> using Map = std::unordered_map<K, V>;
#endif

static const u32 BOS = 0, EOS = 1;
static const u32 SLOT = 0xFFFFFFFFu;
static const u32 MAX_ID = (1u << 21) - 1;  // trigram keys pack three 21-bit ids

// ─────────────────────────────────────────────
// Vocabulary: string ↔ integer id (the "map" that replaces hashing)
// ─────────────────────────────────────────────
struct Vocab {
    Map<std::string, u32> id;
    std::vector<std::string> str;
    std::vector<uint8_t> space;  // 1 if token is whitespace (kept for lossless unroll, skipped by counts)
    Vocab() { get("<s>"); get("</s>"); }
    u32 get(const std::string& s) {
        auto it = id.find(s);
        if (it != id.end()) return it->second;
        u32 k = (u32)str.size();
        if (k > MAX_ID) { std::fprintf(stderr, "vocab limit reached\n"); std::exit(1); }
        id.emplace(s, k); str.push_back(s);
        space.push_back(!s.empty() && (s[0] == ' ' || s[0] == '\t'));
        return k;
    }
    long find(const std::string& s) const { auto it = id.find(s); return it == id.end() ? -1 : (long)it->second; }
    void clear() { id.clear(); str.clear(); space.clear(); get("<s>"); get("</s>"); }
};

static bool wordChar(unsigned char c) { return std::isalnum(c) || c == '_' || c >= 128; }
// Lossless tokenizer: word runs, whitespace runs, or single other bytes.
static std::vector<std::string> tokenize(const std::string& t) {
    std::vector<std::string> out; size_t i = 0, n = t.size();
    while (i < n) {
        unsigned char c = t[i]; size_t j = i + 1;
        if (wordChar(c)) while (j < n && wordChar(t[j])) ++j;
        else if (c == ' ' || c == '\t') while (j < n && (t[j] == ' ' || t[j] == '\t')) ++j;
        out.emplace_back(t.substr(i, j - i)); i = j;
    }
    return out;
}

// ─────────────────────────────────────────────
// Online grammar (Sequitur, Nevill-Manning & Witten 1997)
//   invariant 1: no pair of adjacent symbols appears twice
//   invariant 2: every rule is used at least twice
//   Rule identity = the pair map `dig`, keyed by the two symbol codes.
// ─────────────────────────────────────────────
enum : uint8_t { TERM = 0, NONTERM = 1, GUARD = 2, SEP = 3 };
struct Sym { Sym* n = nullptr; Sym* p = nullptr; u32 v = 0; uint8_t kind = TERM; };

struct Grammar {
    struct RuleRec { Sym* guard = nullptr; u32 refs = 0; };
    std::vector<RuleRec> rules;
    std::vector<u32> freeRules;
    Map<u64, Sym*> dig;
    u32 S = 0;
    size_t liveSyms = 0;

    Grammar() { S = newRule(); }

    static bool ign(const Sym* s) { return s->kind >= GUARD; }
    static u64 code(const Sym* s) { return (u64(s->v) << 1) | (s->kind == NONTERM ? 1u : 0u); }
    static u64 key(const Sym* s) { return (code(s) << 32) | code(s->n); }
    static bool same(const Sym* a, const Sym* b) { return !ign(a) && !ign(b) && a->kind == b->kind && a->v == b->v; }
    Sym* first(u32 r) const { return rules[r].guard->n; }
    Sym* last(u32 r) const { return rules[r].guard->p; }
    size_t ruleCount() const { return rules.size() - freeRules.size() - 1; }

    u32 newRule() {
        u32 r;
        if (!freeRules.empty()) { r = freeRules.back(); freeRules.pop_back(); }
        else { r = (u32)rules.size(); rules.emplace_back(); }
        Sym* g = new Sym; g->kind = GUARD; g->v = r; g->n = g->p = g;
        rules[r].guard = g; rules[r].refs = 0;
        return r;
    }
    Sym* mk(uint8_t kind, u32 v) {
        Sym* s = new Sym; s->kind = kind; s->v = v;
        if (kind == NONTERM) rules[v].refs++;
        if (kind < GUARD) ++liveSyms;
        return s;
    }
    void delDigram(Sym* s) {
        if (ign(s) || ign(s->n)) return;
        auto it = dig.find(key(s));
        if (it != dig.end() && it->second == s) dig.erase(it);
    }
    void join(Sym* l, Sym* r) {
        if (l->n) {
            delDigram(l);
            if (r->p && r->n && same(r, r->p) && same(r, r->n)) dig[key(r)] = r;
            if (l->p && l->n && same(l, l->n) && same(l, l->p)) dig[key(l->p)] = l->p;
        }
        l->n = r; r->p = l;
    }
    void insertAfter(Sym* s, Sym* y) { join(y, s->n); join(s, y); }
    void remove(Sym* s) {
        join(s->p, s->n);
        if (!ign(s)) { delDigram(s); if (s->kind == NONTERM) rules[s->v].refs--; --liveSyms; }
        delete s;
    }
    bool check(Sym* s) {
        if (ign(s) || ign(s->n)) return false;
        u64 k = key(s);
        auto it = dig.find(k);
        if (it == dig.end()) { dig.emplace(k, s); return false; }
        Sym* m = it->second;
        if (m == s) return false;
        if (m->n != s && s->n != m) match(s, m);
        return true;
    }
    void substitute(Sym* s, u32 r) {
        Sym* q = s->p;
        remove(q->n); remove(q->n);
        insertAfter(q, mk(NONTERM, r));
        if (!check(q)) check(q->n);
    }
    void match(Sym* ss, Sym* m) {
        u32 r;
        if (m->p->kind == GUARD && m->n->n->kind == GUARD) {  // pair is already a whole rule: reuse it
            r = m->p->v; substitute(ss, r);
        } else {                                             // new rule for the repeated pair
            r = newRule();
            insertAfter(last(r), mk(ss->kind, ss->v));
            insertAfter(last(r), mk(ss->n->kind, ss->n->v));
            substitute(m, r);
            substitute(ss, r);
            dig[key(first(r))] = first(r);
        }
        Sym* f = first(r);
        if (f->kind == NONTERM && rules[f->v].refs == 1) expand(f);  // rule utility
    }
    void expand(Sym* s) {  // inline a rule that is now used only once
        Sym* left = s->p; Sym* right = s->n; u32 r = s->v;
        Sym* f = first(r); Sym* l = last(r);
        delDigram(left); delDigram(s);
        delete rules[r].guard; rules[r].guard = nullptr; rules[r].refs = 0; freeRules.push_back(r);
        delete s; --liveSyms;
        left->n = f; f->p = left; l->n = right; right->p = l;
        if (!ign(l) && !ign(right)) { u64 k = key(l); if (!dig.count(k)) dig.emplace(k, l); }
    }
    void appendTok(u32 t) { Sym* s = mk(TERM, t); insertAfter(last(S), s); check(s->p); }
    Sym* appendSep(u32 rec) { Sym* s = new Sym; s->kind = SEP; s->v = rec; insertAfter(last(S), s); return s; }
    void emit(const Sym* s, std::vector<u32>& out) const {
        if (s->kind == TERM) out.push_back(s->v);
        else if (s->kind == NONTERM)
            for (const Sym* x = rules[s->v].guard->n; x->kind != GUARD; x = x->n) emit(x, out);
    }
    void clear() {
        for (auto& rr : rules) if (rr.guard) {
            Sym* x = rr.guard->n;
            while (x != rr.guard) { Sym* nx = x->n; delete x; x = nx; }
            delete rr.guard;
        }
        rules.clear(); freeRules.clear(); dig.clear(); liveSyms = 0; S = newRule();
    }
};

// ─────────────────────────────────────────────
// N-gram counts (evidence only — no weights)
// ─────────────────────────────────────────────
static inline u64 pk2(u64 a, u64 b) { return (a << 32) | b; }
static inline u64 pk3(u64 a, u64 b, u64 c) { return (a << 42) | (b << 21) | c; }

struct Counts {
    std::vector<u64> uni; u64 N = 0; u64 uniTypes = 0;
    std::vector<u64> tot2, typ2;
    Map<u64, u64> big, tri, tot3, typ3;
    void grow(size_t n) { if (uni.size() < n) { uni.resize(n); tot2.resize(n); typ2.resize(n); } }
    void add(u32 a, u32 b, u32 w, u64 c) {
        grow(std::max({a, b, w}) + 1);
        if (uni[w] == 0) ++uniTypes;
        uni[w] += c; N += c;
        u64& bc = big[pk2(b, w)]; if (bc == 0) ++typ2[b]; bc += c; tot2[b] += c;
        u64& tc = tri[pk3(a, b, w)]; if (tc == 0) ++typ3[pk2(a, b)]; tc += c; tot3[pk2(a, b)] += c;
    }
    void sub(u32 a, u32 b, u32 w, u64 c) {   // inverse of add, used by RETRACT
        uni[w] -= c; N -= c; if (uni[w] == 0) --uniTypes;
        auto bi = big.find(pk2(b, w)); bi->second -= c; tot2[b] -= c; if (bi->second == 0) { big.erase(bi); --typ2[b]; }
        auto ti = tri.find(pk3(a, b, w)); ti->second -= c; tot3[pk2(a, b)] -= c;
        if (ti->second == 0) { tri.erase(ti); if (--typ3[pk2(a, b)] == 0) { typ3.erase(pk2(a, b)); tot3.erase(pk2(a, b)); } }
    }
    static u64 get(const Map<u64, u64>& m, u64 k) { auto it = m.find(k); return it == m.end() ? 0 : it->second; }
    // Witten–Bell interpolation, order 3 → 2 → 1 → uniform. Computed, never stored.
    double p(u32 w, u32 a, u32 b) const {
        double pr = 1.0 / double(uniTypes + 1);
        if (N) { double lam = double(N) / double(N + uniTypes); pr = lam * double(w < uni.size() ? uni[w] : 0) / double(N) + (1 - lam) * pr; }
        if (b < tot2.size() && tot2[b]) { double t = tot2[b], ty = typ2[b], lam = t / (t + ty); pr = lam * double(get(big, pk2(b, w))) / t + (1 - lam) * pr; }
        auto it = tot3.find(pk2(a, b));
        if (it != tot3.end() && it->second) { double t = it->second, ty = double(get(typ3, pk2(a, b))), lam = t / (t + ty); pr = lam * double(get(tri, pk3(a, b, w))) / t + (1 - lam) * pr; }
        return pr;
    }
    void clear() { *this = Counts(); }
};

// ─────────────────────────────────────────────
// Relations and rules (inference layer data)
// ─────────────────────────────────────────────
struct Relation {
    std::vector<u32> tmpl;         // content tokens, SLOT at the two argument positions
    std::set<std::pair<u32, u32>> stated;
    std::map<std::pair<u32, u32>, std::pair<double, std::string>> derived;  // fact → (score, explanation)
    std::set<std::pair<u32, u32>> lawDerived;   // derived only through law-tier rules (LABELS)
    // declarative amendments: what the evidence says about stated facts that are no longer current
    std::map<std::pair<u32, u32>, std::string> superseded;   // fact -> provenance ("superseded by ev (change|correction)")
    std::map<std::pair<u32, u32>, std::string> withdrawn;    // fact -> provenance
    std::map<u32, std::string> unknownSubj;                  // subject -> why its current value cannot be determined
    std::map<u32, std::string> contradicted;                 // subject -> why (several stated values, no amendment explains them)
    std::map<std::pair<u32, u32>, std::string> viaEvent;     // current fact -> event that set it
    std::map<u32, std::string> disagree;                     // subject -> independent sources give different values (one-value relation)
    std::map<u32, std::string> uncertain;                    // subject -> a newer partial update gave a different value
    std::map<std::pair<u32, u32>, std::string> prov;         // current fact -> which sources assert it
    std::vector<std::tuple<u32, u32, std::string, int>> histLines;   // subject, value, text, kind (1 past, 2 never)
    std::map<std::pair<u32, u32>, u64> reports;              // VOTE (studies/noise): how many records state each fact
    std::map<std::pair<u32, u32>, std::string> outvoted;     // VOTE: stated facts outvoted by a value reported more often
    std::set<u32> disputed;                                  // VOTE: subjects of a one-value relation whose reports have no majority
    std::map<std::pair<u32, u32>, std::string> quarantined;  // QUARANTINE: stated facts two rules contradict, kept out of the evidence
    std::map<std::pair<u32, u32>, std::pair<int, int>> chain; // every derived fact: (inference round, tendency-tier steps in its proof)
};
struct TBranch { int r, s; u32 k; };   // tree branch: R(g,k) when s < 0, else R(g,y) & S(y,k)
inline bool operator<(const TBranch& a, const TBranch& b) { return std::tie(a.r, a.s, a.k) < std::tie(b.r, b.s, b.k); }
inline bool operator==(const TBranch& a, const TBranch& b) { return a.r == b.r && a.s == b.s && a.k == b.k; }
struct RuleH {
    char type;          // 'I' inverse/symmetric, 'T' transitive, 'C' composition
    int r1, r2, r3;     // premise relations, conclusion relation
    u64 n = 0, k = 0;   // chains seen, chains whose conclusion is also stated
    double rate = 0, base = 0, lift = 0; u64 pn = 0; double pca = 0; bool accepted = false;
    double cov = -1, rel = 0; bool law = false;   // completeness used, reliability, label
    std::vector<int> path;                        // multi-premise study: 'P' rules, premise relations in order (CHAIN >= 3)
    int condRel = -1; std::set<u32> condVals, condSubj;   // CONDITIONS: fires only for head subjects with a value in condVals
    bool anchorInv = false; u32 headVal = 0; std::vector<TBranch> branches;   // TREES ('G'): A(x,g) or A(g,x) & branches(g) => T(x, headVal)
    std::string repl;                             // REPLICATE (studies/noise): why the rule was rejected on replication
};

// ─────────────────────────────────────────────
//  VAULT
// ─────────────────────────────────────────────
struct Rec { Sym* sep; u64 count; };

struct Vault {
    Vocab voc; Grammar g; std::vector<Rec> recs;
    std::map<std::vector<u32>, u32> byText;   // exact identity: the token sequence itself is the key
    Counts wc;                                // word counts (the only "training")
    u64 tokensIngested = 0, recordsIngested = 0;

    // ---- derived on demand (cleared by every ingest) ----
    bool dirty = true; double classThresh = 0.5;
    std::vector<u32> cls; std::vector<u32> clsSize; Counts cc;
    std::vector<Relation> rels; std::vector<RuleH> ruleList;
    bool inferred = false;
    double LIFT_MIN = 5.0, RATE_MIN = 0.4, PCA_MIN = 0.8; u64 K_MIN = 3;
    std::vector<std::tuple<int, u32, u32, u32, std::string>> conflicts;
    // v2.1 behaviours (on by default; all four off == v2.0 behaviour)
    int F_COV = 1, F_LABELS = 1, F_CORROB = 1, F_PROFILE = 0;
    double RATE_REL = 0.8, LAW_MIN = 0.95, covGlobal = -1;
    std::vector<double> covRel;
    std::set<u32> touched;   // subjects affected by UPDATE (enables change-triggered staleness checks)
    int F_STALE = 1;  // rel, subject, stated obj, inferred obj, proof
    int DEPTH = 4, lastRounds = 0;   // multi-premise study: inference rounds (0 = until nothing new)
    int CHAIN_L = 2;                 // longest rule body (2 = shipped shapes; >= 3 adds evidence-guided path rules)
    int F_COND = 0;                  // learn conditions that restrict an accepted rule to a group of subjects
    int F_TSTEPS = -1;               // TENDENCYSTEPS (studies/tendency): most tendency-tier rule steps a proof may contain; -1 = no limit
    u64 MAX_WORDS = 12000;           // categories are built for this many most frequent words; rarer words are not slots
    u64 MAX_RELS = 40;               // relations kept, largest first
    u64 wordsSeen = 0, relsSeen = 0; // before those caps (reported when a cap is hit)
    int F_REPL = 0;                  // REPLICATE (studies/noise): a rule must also pass in each half of its subjects
    int F_VOTE = 0;                  // VOTE (studies/noise): in a one-value relation, the value reported most outvotes the rest
    int F_QUAR = 0;                  // QUARANTINE (studies/noise): stated facts two rules contradict are kept out of the evidence
    std::vector<std::set<std::pair<u32, u32>>>* capture = nullptr;   // REPLICATE: each rule's predictions from stated facts
    std::vector<std::tuple<int, u32, u32, u32, std::string>> quarList;   // QUARANTINE: the facts kept out, reported as conflicts
    std::vector<std::tuple<int, u32, u32, u32, std::string>> voteList;   // VOTE: outvoted facts, reported as conflicts
    u64 replRejected = 0;
    int F_CSTREAM = 0;               // CLUSTERSTREAM (studies/scaling): join similar categories as they are found; same categories, no pair list
    int F_TREES = 0;                 // tree-shaped rules (studies/trees): several branches joined at one entity
    // ---- declarative amendments (experimental condition C) ----
    int F_DECL = 0;        // amendment-record interpretation from the earlier study: off in this build
    // ---- source-aware evidence (condition D) ----
    int F_OBS = 1;     // project the observation log (only matters once OBSERVE has been used)
    int F_DX = 0;
    int F_CHG_REMOVALS = 1;   // v2.2: only records that lost or replaced a fact feed the change signal
    int F_SAMEFIX = 1;        // v2.2: a stale-candidate re-derived to the same value by its own rule is confirmed, not 'unknown'
    double F_REFRESH = 0;     // v2.2: reuse classes and mined rules while changes since the last full build are <= this share of records and add no new words (0 = always full)
    struct CachedRule { RuleH h; std::vector<u32> t1, t2, t3; };
    std::vector<CachedRule> ruleCache; bool haveCache = false; size_t vocAtFull = 0; u64 recsAtFull = 0; u64 fullBuilds = 0, refreshBuilds = 0;      // D-x: apply the dependency trace / same-rule re-derivation to facts that left a record's state
    struct Obs { std::string src, key; long t = 0, rev = 0; bool snap = true; std::vector<u32> rids; u64 seq = 0; };
    std::vector<Obs> obsLog;
    std::set<u32> curRids, sourcedRids;
    std::map<u32, std::set<std::string>> curSrc;   // current record -> sources that currently assert it
    struct HistE { std::string src, key; long tFrom, tTo, rev, byRev; bool never; };
    std::map<u32, std::vector<HistE>> histOf;      // record -> history entries
    std::map<u32, std::vector<std::pair<std::string, long>>> partialLate;   // record -> (source, time) of partial observations after the record's first time
    std::map<u32, long> curSince;                  // current record -> time it entered its source's state (earliest across sources)
    std::set<std::string> changedKeys;
    void project() {
        curRids.clear(); sourcedRids.clear(); curSrc.clear(); histOf.clear(); partialLate.clear(); curSince.clear(); changedKeys.clear();
        std::map<std::pair<std::string, std::string>, std::vector<const Obs*>> byRec;
        for (auto& o : obsLog) { byRec[{o.src, o.key}].push_back(&o); for (u32 r : o.rids) sourcedRids.insert(r); }
        for (auto& br : byRec) {
            auto v = br.second;
            std::stable_sort(v.begin(), v.end(), [](const Obs* a, const Obs* b) { return a->t != b->t ? a->t < b->t : a->rev < b->rev; });
            std::map<long, std::vector<const Obs*>> byT; for (auto* o : v) byT[o->t].push_back(o);
            std::set<u32> state; std::map<u32, long> since; long firstT = byT.begin()->first; bool changed = false;
            for (auto& bt : byT) {
                long t = bt.first; auto& os = bt.second;
                long topRev = os.back()->rev;
                std::set<u32> eff;   // the highest revision at this time is what this time says; partials at that revision add up
                bool snap = false;
                for (auto* o : os) if (o->rev == topRev) { if (o->snap) snap = true; eff.insert(o->rids.begin(), o->rids.end()); }
                for (auto* o : os) if (o->rev < topRev) for (u32 r : o->rids) if (!eff.count(r))   // corrected at the same time: never held
                    histOf[r].push_back({br.first.first, br.first.second, t, t, o->rev, topRev, true});
                std::set<u32> next = snap ? eff : state;
                if (!snap) { next.insert(eff.begin(), eff.end()); if (t > firstT) for (u32 r : eff) if (!state.count(r)) partialLate[r].push_back({br.first.first, t}); }
                for (u32 r : state) if (!next.count(r)) { histOf[r].push_back({br.first.first, br.first.second, since[r], t, 0, 0, false}); changed = true; }
                for (u32 r : next) if (!state.count(r)) { since[r] = t; if (t > firstT && !F_CHG_REMOVALS) changed = true; }
                state = next;
            }
            for (u32 r : state) { curRids.insert(r); curSrc[r].insert(br.first.first); auto cs = curSince.find(r); if (cs == curSince.end() || since[r] < cs->second) curSince[r] = since[r]; }
            if (changed) changedKeys.insert(br.first.second);
        }
    }
    bool observedNow(u32 rid) const { return obsLog.empty() || !sourcedRids.count(rid) || curRids.count(rid); }
    int F_DECLFN = 0;      // follow-up: values explained by a subject's own amendment evidence do not count against the one-value test
    int F_DECL_MINE = 0;   // 1 = amendment records also feed relations and rules (C1); 0 = stored only (C2)
    struct Event { u32 id = 0, subj = 0, oldv = 0, newv = 0; bool hasS = false, hasO = false, hasN = false, corr = false, withdrawn = false; std::vector<u32> follows; std::vector<u32> withdrawnBy; };
    std::map<u32, Event> events;
    struct SupSrc { std::string oldText, newText, evid; char kind; };
    std::vector<SupSrc> supSrc;
    std::vector<std::tuple<int, u32, u32, int>> supFacts;      // rel, subject, old value, supSrc index
    std::map<std::string, int> depFacts; std::map<std::string, std::string> depRule; std::set<u32> depSubj;
    std::map<std::pair<int, u32>, std::pair<u32, std::string>> staleAlt;
    std::vector<std::string> unresolved;
    bool isAmendRecord(const std::vector<u32>& c) const {
        if (c.size() != 3) return false;
        const std::string& k = voc.str[c[1]];
        return k == "amends" || k == "replaces" || k == "sets" || k == "follows" || k == "withdraws" || (k == "is" && voc.str[c[2]] == "correction");
    }
    int isDep(int ri, u32 a, u32 b) const {
        if (depFacts.empty() || (!depSubj.count(a) && !depSubj.count(b))) return -1;
        auto it = depFacts.find(renderFact(rels[ri], a, b)); return it == depFacts.end() ? -1 : it->second;
    }

    // ── INGEST ──────────────────────────────────
    std::vector<u32> toIds(const std::string& text) {
        std::vector<u32> ids; for (auto& t : tokenize(text)) ids.push_back(voc.get(t)); return ids;
    }
    void countContent(const std::vector<u32>& ids, u64 c) {
        u32 a = BOS, b = BOS;
        for (u32 w : ids) { if (voc.space[w]) continue; wc.add(a, b, w, c); a = b; b = w; }
        wc.add(a, b, EOS, c);
    }
    void uncountContent(const std::vector<u32>& ids, u64 c) {
        u32 a = BOS, b = BOS;
        for (u32 w : ids) { if (voc.space[w]) continue; wc.sub(a, b, w, c); a = b; b = w; }
        wc.sub(a, b, EOS, c);
    }
    bool retractIds(const std::vector<u32>& ids) {   // tombstone a record and remove its evidence
        auto it = byText.find(ids); if (it == byText.end()) return false;
        u32 r = it->second; uncountContent(ids, recs[r].count); recordsIngested -= recs[r].count;
        recs[r].count = 0; byText.erase(it); dirty = true; inferred = false; return true;
    }
    long ingest(const std::string& text) {
        std::vector<u32> ids = toIds(text);
        if (ids.empty()) return -1;
        ++recordsIngested;
        u32 rid;
        auto it = byText.find(ids);
        if (it != byText.end()) { rid = it->second; recs[rid].count++; }
        else {
            for (u32 t : ids) g.appendTok(t);
            Sym* sep = g.appendSep((u32)recs.size());
            rid = (u32)recs.size(); recs.push_back({sep, 1}); byText.emplace(ids, rid);
            tokensIngested += ids.size();
        }
        countContent(ids, 1);
        dirty = true; inferred = false;
        return rid;
    }
    std::vector<u32> recIds(u32 r) const {
        std::vector<u32> out;
        Sym* s = (r == 0) ? g.first(g.S) : recs[r - 1].sep->n;
        for (; s != recs[r].sep; s = s->n) g.emit(s, out);
        return out;
    }
    std::string render(const std::vector<u32>& ids) const { std::string s; for (u32 t : ids) s += voc.str[t]; return s; }
    std::string unroll(u32 r) const { return render(recIds(r)); }
    std::vector<u32> content(const std::vector<u32>& ids) const { std::vector<u32> o; for (u32 t : ids) if (!voc.space[t]) o.push_back(t); return o; }
    std::string words(const std::vector<u32>& ids) const {
        std::string s; for (size_t i = 0; i < ids.size(); ++i) { if (i) s += ' '; s += ids[i] == SLOT ? "?" : voc.str[ids[i]]; } return s;
    }

    // ── LAYER 2: categories from context counts (derived, not stored as weights) ──
    void buildClasses() {
        size_t maxWords = MAX_WORDS;
        size_t V = voc.str.size();
        cls.assign(V, 0); for (u32 i = 0; i < V; ++i) cls[i] = i;
        std::vector<u32> wordsv;
        for (u32 w = 2; w < V; ++w) if (w < wc.uni.size() && wc.uni[w] && !voc.space[w]) wordsv.push_back(w);
        std::sort(wordsv.begin(), wordsv.end(), [&](u32 a, u32 b) { return wc.uni[a] > wc.uni[b]; });
        wordsSeen = wordsv.size();
        if (wordsv.size() > maxWords) wordsv.resize(maxWords);
        std::vector<std::vector<std::pair<u32, u64>>> L(V), R(V);
        for (auto& kv : wc.big) { u32 b = u32(kv.first >> 32), w = u32(kv.first & 0xFFFFFFFFu); L[w].push_back({b, kv.second}); R[b].push_back({w, kv.second}); }
        using Sig = std::vector<std::pair<u32, double>>;
        auto cosv = [](const Sig& a, double na, const Sig& b, double nb) {
            if (na == 0 || nb == 0) return 0.0;
            double d = 0; size_t i = 0, j = 0;
            while (i < a.size() && j < b.size()) { if (a[i].first == b[j].first) { d += a[i].second * b[j].second; ++i; ++j; } else if (a[i].first < b[j].first) ++i; else ++j; }
            return d / (na * nb);
        };
        for (int round = 0; round < 4; ++round) {
            std::map<u32, std::vector<u32>> members;
            for (u32 w : wordsv) members[cls[w]].push_back(w);
            std::vector<u32> ids; std::vector<Sig> sl, sr; std::vector<double> nl, nr;
            for (auto& m : members) {
                std::map<u32, double> l, r;
                for (u32 w : m.second) { for (auto& x : L[w]) l[cls[x.first]] += double(x.second); for (auto& x : R[w]) r[cls[x.first]] += double(x.second); }
                Sig a(l.begin(), l.end()), b(r.begin(), r.end());
                double na = 0, nb = 0; for (auto& x : a) na += x.second * x.second; for (auto& x : b) nb += x.second * x.second;
                ids.push_back(m.first); sl.push_back(std::move(a)); sr.push_back(std::move(b)); nl.push_back(std::sqrt(na)); nr.push_back(std::sqrt(nb));
            }
            size_t K = ids.size();
            if (F_CSTREAM) {   // CLUSTERSTREAM (studies/scaling). The listed-pairs path below computes connected components of the
                               // graph of pairs at or above the threshold (single linkage). Components do not depend on the order of
                               // joins, and a pair already in one component joins nothing, so join each pair as it is found and skip
                               // pairs already joined. Roots stay the smallest index of their component (uf[max] = min), so class ids
                               // are identical; a round stops when nothing joined, exactly when the pair list would have been empty.
                               // Memory drops from one entry per similar pair to one per class; the comparisons stay K^2/2.
                std::vector<u32> uf(K); std::iota(uf.begin(), uf.end(), 0);
                std::function<u32(u32)> find = [&](u32 x) { return uf[x] == x ? x : uf[x] = find(uf[x]); };
                bool any = false;
                for (u32 i = 0; i < K; ++i) for (u32 j = i + 1; j < K; ++j) {
                    u32 a = find(i), b = find(j); if (a == b) continue;
                    double s1 = cosv(sl[i], nl[i], sl[j], nl[j]); if (s1 < classThresh) continue;
                    double s2 = cosv(sr[i], nr[i], sr[j], nr[j]);
                    if (std::min(s1, s2) >= classThresh) { uf[std::max(a, b)] = std::min(a, b); any = true; }
                }
                if (!any) break;
                std::map<u32, u32> newId;
                for (u32 i = 0; i < K; ++i) { u32 root = find(i); u32 rep = ids[root]; newId[ids[i]] = rep; }
                for (u32 w : wordsv) cls[w] = newId[cls[w]];
                continue;
            }
            std::vector<std::tuple<double, u32, u32>> pairs;
            for (u32 i = 0; i < K; ++i) for (u32 j = i + 1; j < K; ++j) {
                double s1 = cosv(sl[i], nl[i], sl[j], nl[j]); if (s1 < classThresh) continue;
                double s2 = cosv(sr[i], nr[i], sr[j], nr[j]); double s = std::min(s1, s2);
                if (s >= classThresh) pairs.emplace_back(s, i, j);
            }
            if (pairs.empty()) break;
            std::sort(pairs.begin(), pairs.end(), [](auto& x, auto& y) { return std::get<0>(x) > std::get<0>(y); });
            std::vector<u32> uf(K); std::iota(uf.begin(), uf.end(), 0);
            std::function<u32(u32)> find = [&](u32 x) { return uf[x] == x ? x : uf[x] = find(uf[x]); };
            for (auto& t : pairs) { u32 a = find(std::get<1>(t)), b = find(std::get<2>(t)); if (a != b) uf[std::max(a, b)] = std::min(a, b); }
            std::map<u32, u32> newId;
            for (u32 i = 0; i < K; ++i) { u32 root = find(i); u32 rep = ids[root]; newId[ids[i]] = rep; }
            for (u32 w : wordsv) cls[w] = newId[cls[w]];
        }
        clsSize.assign(V, 0); for (u32 w : wordsv) clsSize[cls[w]]++;
        cc.clear();
        for (auto& kv : wc.tri) {
            u32 a = u32(kv.first >> 42), b = u32((kv.first >> 21) & MAX_ID), w = u32(kv.first & MAX_ID);
            cc.add(cls[a], cls[b], cls[w], kv.second);
        }
    }
    bool open(u32 w) const { return w < clsSize.size() && w < cls.size() && clsSize[cls[w]] >= 2; }

    // probabilities: word model, class model, and their mixture — all from counts
    double pClass(u32 w, u32 a, u32 b) const {
        if (w >= wc.uni.size() || !wc.uni[w]) return 1e-9;
        u32 c = cls[w]; double emit = double(wc.uni[w]) / double(cc.uni[c]);
        return cc.p(c, cls[a], cls[b]) * emit;
    }
    double pMix(u32 w, u32 a, u32 b) const { return 0.5 * wc.p(w, a, b) + 0.5 * pClass(w, a, b); }

    // ── LAYER 3: relation templates (two-argument patterns) ──
    void buildRelations() {
        rels.clear();
        std::map<std::vector<u32>, u64> support;
        std::vector<std::vector<u32>> recContent;
        events.clear();
        bool useObs = F_OBS && !obsLog.empty();
        if (useObs) project();
        std::vector<u32> recRid;
        for (u32 r = 0; r < recs.size(); ++r) if (recs[r].count) {
            if (useObs && !observedNow(r)) continue;   // only currently supported evidence takes part in relations and rules
            auto c = content(recIds(r));
            if (F_DECL && isAmendRecord(c)) {
                auto& e = events[c[0]]; e.id = c[0]; const std::string& k = voc.str[c[1]];
                if (k == "amends") { e.subj = c[2]; e.hasS = true; } else if (k == "replaces") { e.oldv = c[2]; e.hasO = true; }
                else if (k == "sets") { e.newv = c[2]; e.hasN = true; } else if (k == "is") e.corr = true;
                else if (k == "follows") e.follows.push_back(c[2]); else if (k == "withdraws") events[c[2]].withdrawnBy.push_back(c[0]);
                if (!F_DECL_MINE) continue;   // C2: amendment evidence is stored, not mined
            }
            recContent.push_back(c); recRid.push_back(r);
        }
        auto keyFor = [&](const std::vector<u32>& c, size_t i, size_t j) { auto k = c; k[i] = SLOT; k[j] = SLOT; return k; };
        auto openPos = [&](const std::vector<u32>& c) { std::vector<size_t> p; for (size_t i = 0; i < c.size(); ++i) if (open(c[i])) p.push_back(i); return p; };
        for (auto& c : recContent) {
            auto p = openPos(c); if (p.size() < 2 || p.size() > 8) continue;
            for (size_t x = 0; x < p.size(); ++x) for (size_t y = x + 1; y < p.size(); ++y) support[keyFor(c, p[x], p[y])]++;
        }
        std::map<std::vector<u32>, int> relIdx;
        for (size_t ci = 0; ci < recContent.size(); ++ci) {
            auto& c = recContent[ci];
            auto p = openPos(c); if (p.size() < 2 || p.size() > 8) continue;
            u64 best = 0; size_t bi = 0, bj = 0;
            for (size_t x = 0; x < p.size(); ++x) for (size_t y = x + 1; y < p.size(); ++y) {
                u64 s = support[keyFor(c, p[x], p[y])]; if (s > best) { best = s; bi = p[x]; bj = p[y]; }
            }
            if (best < 3) continue;
            auto k = keyFor(c, bi, bj);
            auto it = relIdx.find(k); int ri;
            if (it == relIdx.end()) { ri = (int)rels.size(); relIdx[k] = ri; rels.push_back({k, {}, {}}); } else ri = it->second;
            rels[ri].stated.insert({c[bi], c[bj]});
            if (F_VOTE) rels[ri].reports[{c[bi], c[bj]}] += recs[recRid[ci]].count;
        }
        std::sort(rels.begin(), rels.end(), [](auto& a, auto& b) { return a.stated.size() > b.stated.size(); });
        relsSeen = rels.size();
        if (rels.size() > MAX_RELS) rels.resize(MAX_RELS);
        if (F_VOTE) applyVote(); else voteList.clear();
        if (F_DECL) interpretAmendments();
        if (useObs) annotateObservations(support);
    }

    // ── VOTE (studies/noise): repeated reports in a one-value relation. A value reported more often than all the subject's
    //    other values together (and at least twice) outvotes them; the outvoted facts are kept out of the evidence and reported.
    //    Only relations where at least half the subjects have a value reported twice or more take part, and a relation where 10% or more of the
    //    subjects with several values have two values each reported twice is many-value: skipped. ──
    void applyVote() {
        voteList.clear();
        for (size_t ri = 0; ri < rels.size(); ++ri) {
            auto& R = rels[ri];
            R.outvoted.clear(); R.disputed.clear();
            std::map<u32, std::vector<std::pair<u64, u32>>> per;
            for (auto& f : R.stated) { auto it = R.reports.find(f); per[f.first].push_back({it == R.reports.end() ? 1 : it->second, f.second}); }
            auto decide = [](std::vector<std::pair<u64, u32>>& v) {   // sorts v, most reported first; true if v[0] outvotes the rest
                if (v.size() == 1) return true;
                std::sort(v.begin(), v.end(), [](auto& x, auto& y) { return x.first != y.first ? x.first > y.first : x.second < y.second; });
                u64 rest = 0; for (size_t i = 1; i < v.size(); ++i) rest += v[i].first;
                return v[0].first > rest && v[0].first >= 2;
            };
            // a many-value relation shows subjects with two or more values that are each reported at least twice; skip those
            size_t multi = 0, twoStrong = 0;
            for (auto& p : per) if (p.second.size() > 1) { ++multi; int strong = 0; for (auto& v : p.second) if (v.first >= 2) ++strong; if (strong >= 2) ++twoStrong; }
            size_t repeated = 0;   // subjects with some value reported twice or more
            for (auto& p : per) for (auto& v : p.second) if (v.first >= 2) { ++repeated; break; }
            if (2 * repeated < per.size()) continue;   // fewer than half the subjects have repeated reports: nothing to vote with
            if (per.size() < 5 || (multi > 0 && double(twoStrong) >= 0.1 * double(multi))) continue;
            for (auto& p : per) decide(p.second);
            for (auto& p : per) {
                auto& v = p.second; if (v.size() < 2) continue;
                if (!decide(v)) { R.disputed.insert(p.first); continue; }   // no majority: both stay, reported, and ignored by the one-value test
                for (size_t i = 1; i < v.size(); ++i) {
                    R.outvoted[{p.first, v[i].second}] = "OUTVOTED: reported " + std::to_string(v[i].first) + "x, while \"" + renderFact(R, p.first, v[0].second) + "\" is reported " + std::to_string(v[0].first) + "x";
                    R.stated.erase({p.first, v[i].second});
                    voteList.emplace_back((int)ri, p.first, v[i].second, v[0].second, R.outvoted[{p.first, v[i].second}]);
                }
            }
        }
    }

    // ── neutral annotations from the observation log: provenance, history, disagreement, uncertainty. Nothing is resolved here. ──
    void annotateObservations(std::map<std::vector<u32>, u64>& support) {
        supSrc.clear(); supFacts.clear();
        std::map<std::vector<u32>, int> tIdx; for (size_t i = 0; i < rels.size(); ++i) tIdx[rels[i].tmpl] = (int)i;
        auto pairOf = [&](u32 rid, int& ri, u32& a, u32& b) {   // which relation a record falls in (same rule as relation building)
            auto c = content(recIds(rid));
            std::vector<size_t> p; for (size_t i = 0; i < c.size(); ++i) if (open(c[i])) p.push_back(i);
            if (p.size() < 2 || p.size() > 8) return false;
            u64 best = 0; size_t bi = 0, bj = 0;
            for (size_t x = 0; x < p.size(); ++x) for (size_t y = x + 1; y < p.size(); ++y) {
                auto k = c; k[p[x]] = SLOT; k[p[y]] = SLOT; auto it = support.find(k); u64 sp = it == support.end() ? 0 : it->second;
                if (sp > best) { best = sp; bi = p[x]; bj = p[y]; }
            }
            if (best < 3) return false;
            auto k = c; k[bi] = SLOT; k[bj] = SLOT; auto it = tIdx.find(k); if (it == tIdx.end()) return false;
            ri = it->second; a = c[bi]; b = c[bj]; return true;
        };
        std::vector<bool> fn(rels.size());
        for (size_t i = 0; i < rels.size(); ++i) {
            std::map<u32, int> per; for (auto& f : rels[i].stated) per[f.first]++;
            size_t single = 0; for (auto& x : per) if (x.second == 1) ++single;
            fn[i] = per.size() >= 5 && double(single) / double(per.size()) >= 0.9;
        }
        std::map<std::pair<int, u32>, std::map<u32, std::set<std::string>>> vals;   // (rel, subject) -> value -> sources
        std::map<std::pair<int, u32>, std::map<u32, long>> since;
        for (u32 r : curRids) {
            int ri; u32 a, b; if (!pairOf(r, ri, a, b)) continue;
            std::string ps; for (auto& sname : curSrc[r]) ps += (ps.empty() ? "" : ", ") + sname;
            auto& pv = rels[ri].prov[{a, b}]; pv = pv.empty() ? ps : pv + ", " + ps;
            vals[{ri, a}][b].insert(curSrc[r].begin(), curSrc[r].end());
            since[{ri, a}][b] = curSince[r];
        }
        for (u32 r = 0; r < recs.size(); ++r) if (!sourcedRids.count(r) && recs[r].count) {   // facts ingested without an envelope
            int ri; u32 a, b; if (pairOf(r, ri, a, b)) vals[{ri, a}][b].insert("(no source)");
        }
        for (auto& sv : vals) {
            int ri = sv.first.first; u32 a = sv.first.second; auto& m = sv.second;
            if (!fn[ri] || m.size() < 2) continue;
            bool dis = false;   // two values whose asserting sources do not overlap
            for (auto i = m.begin(); i != m.end(); ++i) for (auto j = std::next(i); j != m.end(); ++j) {
                bool overlap = false; for (auto& x : i->second) if (j->second.count(x)) overlap = true;
                if (!overlap) dis = true;
            }
            if (dis) {
                std::string d; for (auto& v : m) { std::string ss; for (auto& x : v.second) ss += (ss.empty() ? "" : "+") + x; d += (d.empty() ? "" : "; ") + ss + " says " + voc.str[v.first]; }
                rels[ri].disagree[a] = d;
            }
        }
        for (auto& pl : partialLate) {   // a newer partial observation gave a different value; the earlier one was not withdrawn
            u32 r = pl.first; if (!curRids.count(r)) continue;
            int ri; u32 a, b; if (!pairOf(r, ri, a, b) || !fn[ri]) continue;
            auto& m = vals[{ri, a}]; if (m.size() < 2 || rels[ri].disagree.count(a)) continue;
            for (auto& v : m) if (v.first != b) {
                rels[ri].uncertain[a] = "a partial update (" + pl.second.front().first + ", t=" + std::to_string(pl.second.front().second) + ") gave " + voc.str[b] +
                                        "; the earlier value " + voc.str[v.first] + " was not withdrawn";
                break;
            }
        }
        for (auto& h : histOf) {   // history lines and, for D-x, facts that left a record's state
            u32 r = h.first; int ri; u32 a, b; if (!pairOf(r, ri, a, b)) continue;
            for (auto& e : h.second) {
                std::string txt = e.never ? "corrected: never held per " + e.src + " (t=" + std::to_string(e.tFrom) + " revision " + std::to_string(e.rev) + " replaced by revision " + std::to_string(e.byRev) + ")"
                                          : "historical: held per " + e.src + " from t=" + std::to_string(e.tFrom) + " until t=" + std::to_string(e.tTo);
                rels[ri].histLines.emplace_back(a, b, txt, e.never ? 2 : 1);
            }
            if (F_DX && !curRids.count(r) && !rels[ri].stated.count({a, b})) {
                std::string now; for (auto& f : rels[ri].stated) if (f.first == a) { now = renderFact(rels[ri], a, f.second); break; }
                supSrc.push_back({renderFact(rels[ri], a, b), now.empty() ? "(no current value)" : now, h.second.front().src, h.second.front().never ? 'X' : 'C'});
                supFacts.emplace_back(ri, a, b, (int)supSrc.size() - 1);
            }
        }
        touched.clear();   // records whose state changed feed the engine's existing change signal (the same hook UPDATE uses)
        for (auto& k : changedKeys) {
            long id = voc.find(k); if (id < 0) continue; touched.insert((u32)id);
            for (auto& R2 : rels) for (auto& f : R2.stated) if (f.second == (u32)id) touched.insert(f.first);
        }
    }

    // ── declarative amendments: decide, from stored evidence only, which stated facts are no longer current ──
    void interpretAmendments() {
        touched.clear(); supSrc.clear(); supFacts.clear(); unresolved.clear();
        for (auto& R : rels) { R.superseded.clear(); R.withdrawn.clear(); R.unknownSubj.clear(); R.contradicted.clear(); R.viaEvent.clear(); }
        std::set<u32> evSubj; for (auto& kv : events) if (kv.second.hasS) evSubj.insert(kv.second.subj);
        std::vector<bool> fn(rels.size());
        std::map<u32, std::set<u32>> evVals; for (auto& kv : events) if (kv.second.hasS) { if (kv.second.hasO) evVals[kv.second.subj].insert(kv.second.oldv); if (kv.second.hasN) evVals[kv.second.subj].insert(kv.second.newv); }
        for (size_t i = 0; i < rels.size(); ++i) {   // one-value relation, judged on subjects without amendment evidence
            std::map<u32, int> per;
            if (F_DECLFN) {   // every subject counts; values its own amendment evidence explains count as one
                std::map<u32, int> expl;
                for (auto& f : rels[i].stated) { auto ev = evVals.find(f.first); if (ev != evVals.end() && ev->second.count(f.second)) expl[f.first] = 1; else per[f.first]++; }
                for (auto& e : expl) per[e.first] += 1;
            } else for (auto& f : rels[i].stated) if (!evSubj.count(f.first)) per[f.first]++;
            size_t single = 0; for (auto& x : per) if (x.second == 1) ++single;
            fn[i] = per.size() >= 5 && double(single) / double(per.size()) >= 0.9;
        }
        // resolve each complete event to the one-value relation that holds the new fact
        std::map<std::pair<int, u32>, std::vector<u32>> groups; std::map<u32, int> evRel;
        for (auto& kv : events) {
            auto& e = kv.second; e.withdrawn = !e.withdrawnBy.empty();
            if (!(e.hasS && e.hasO && e.hasN)) continue;
            std::vector<int> cand;
            for (size_t i = 0; i < rels.size(); ++i) if (fn[i] && rels[i].stated.count({e.subj, e.newv})) cand.push_back((int)i);
            if (cand.size() != 1) { unresolved.push_back(voc.str[e.id] + (cand.empty() ? ": no one-value relation holds the new fact" : ": several relations hold the new fact")); continue; }
            evRel[e.id] = cand[0];
            if (!e.withdrawn) groups[{cand[0], e.subj}].push_back(e.id);
        }
        auto text = [&](int ri, u32 a, u32 b) { return renderFact(rels[ri], a, b); };
        for (auto& g : groups) {
            int ri = g.first.first; u32 x = g.first.second; auto& ids = g.second; auto& R = rels[ri];
            bool anyFollows = false; for (u32 id : ids) if (!events[id].follows.empty()) anyFollows = true;
            std::set<u32> inGroup(ids.begin(), ids.end());
            std::map<u32, std::set<u32>> later;   // id -> events that come after it
            for (u32 a : ids) for (u32 b : ids) if (a != b) {
                auto& ea = events[a]; auto& eb = events[b];
                bool after = anyFollows ? std::count(eb.follows.begin(), eb.follows.end(), a) > 0 : eb.oldv == ea.newv;
                if (after) later[a].insert(b);
            }
            std::vector<u32> last; for (u32 a : ids) if (later[a].empty()) last.push_back(a);
            touched.insert(x); for (auto& R2 : rels) for (auto& f : R2.stated) if (f.second == x) touched.insert(f.first);
            if (last.size() != 1) {
                R.unknownSubj[x] = "the order of " + std::to_string(ids.size()) + " amendments cannot be determined from the evidence";
                continue;
            }
            u32 cur = events[last[0]].newv;
            R.viaEvent[{x, cur}] = voc.str[last[0]];
            for (u32 id : ids) {
                auto& e = events[id];
                std::vector<std::pair<u32, std::string>> olds = {{e.oldv, voc.str[id]}};
                for (auto& o : olds) {
                    if (o.first == cur) continue;
                    std::string prov = "superseded by " + o.second + (e.corr ? " (correction: never held)" : " (change: held until then)");
                    R.superseded[{x, o.first}] = prov;
                    if (R.stated.erase({x, o.first})) {
                        supSrc.push_back({text(ri, x, o.first), text(ri, x, e.newv), voc.str[id], e.corr ? 'X' : 'C'});
                        supFacts.emplace_back(ri, x, o.first, (int)supSrc.size() - 1);
                    }
                }
            }
        }
        // withdrawn events: their new fact loses its only support
        for (auto& kv : events) {
            auto& e = kv.second; if (!e.withdrawn || !evRel.count(e.id)) continue;
            int ri = evRel[e.id]; auto& R = rels[ri];
            bool setByActive = false;
            auto gi = groups.find({ri, e.subj});
            if (gi != groups.end()) for (u32 id : gi->second) if (events[id].newv == e.newv) setByActive = true;
            if (setByActive) continue;
            std::string w; for (u32 b : e.withdrawnBy) w += (w.empty() ? "" : ", ") + voc.str[b];
            R.withdrawn[{e.subj, e.newv}] = "withdrawn: asserted only by " + voc.str[e.id] + " (" + text(ri, e.subj, e.oldv) + " -> " + voc.str[e.newv] + "), which " + w + " withdraws (never held)";
            R.stated.erase({e.subj, e.newv});
        }
        // contradictions: several stated values in a one-value relation that no amendment explains
        for (size_t i = 0; i < rels.size(); ++i) {
            if (!fn[i]) continue;
            std::map<u32, int> per; for (auto& f : rels[i].stated) per[f.first]++;
            for (auto& x : per) if (x.second >= 2 && !groups.count({(int)i, x.first}))
                rels[i].contradicted[x.first] = std::to_string(x.second) + " stated values and no amendment evidence explains the difference";
        }
    }
    std::string renderFact(const Relation& R, u32 a, u32 b) const {
        std::vector<u32> t = R.tmpl; bool firstSlot = true;
        for (auto& x : t) if (x == SLOT) { x = firstSlot ? a : b; firstSlot = false; }
        return words(t);
    }

    // ── LAYER 4: rules between relations, scored by evidence ──
    void mineRules() {
        ruleList.clear();
        size_t m = rels.size();
        std::vector<std::map<u32, std::vector<u32>>> out(m);
        std::vector<double> base(m);
        std::vector<std::set<u32>> subj(m);
        for (size_t i = 0; i < m; ++i) for (auto& f : rels[i].stated) subj[i].insert(f.first);
        for (size_t i = 0; i < m; ++i) {
            std::set<u32> d, r;
            for (auto& f : rels[i].stated) { out[i][f.first].push_back(f.second); d.insert(f.first); r.insert(f.second); }
            base[i] = double(rels[i].stated.size()) / double(std::max<size_t>(1, d.size() * r.size()));
        }
        auto finish = [&](RuleH h) {
            if (h.n == 0) return;
            h.rate = double(h.k) / double(h.n); h.base = base[h.r3];
            h.lift = h.base > 0 ? h.rate / h.base : 0;
            h.pca = h.pn ? double(h.k) / double(h.pn) : 0;
            // classic test, OR partial-completeness test (AMIE): judge the rule only where the subject's answer is known
            bool classic = h.lift >= LIFT_MIN && h.rate >= RATE_MIN;
            double ex = double(h.pn) * h.base, sd = std::sqrt(std::max(1e-9, ex * (1 - h.base)));
            bool pcaOk = h.pn >= 5 && h.pca >= PCA_MIN && (double(h.k) - ex) / sd >= 3.0;   // agreement 3 s.d. above chance
            h.accepted = h.k >= K_MIN && (classic || pcaOk);
            ruleList.push_back(h);
        };
        for (size_t i = 0; i < m; ++i) for (size_t j = 0; j < m; ++j) {  // inverse (i==j: symmetric)
            RuleH h{'I', (int)i, -1, (int)j};
            for (auto& f : rels[i].stated) { if (f.first == f.second) continue; if (F_STALE && (touched.count(f.first) || touched.count(f.second))) continue; h.n++; if (subj[j].count(f.second)) h.pn++; if (rels[j].stated.count({f.second, f.first})) h.k++; }
            finish(h);
        }
        for (size_t i = 0; i < m; ++i) for (size_t j = 0; j < m; ++j) for (size_t k = 0; k < m; ++k) {  // composition
            RuleH h{(i == j && j == k) ? 'T' : 'C', (int)i, (int)j, (int)k};
            for (auto& f : rels[i].stated) {
                if (F_STALE && touched.count(f.first)) continue;   // subjects in flux do not count as evidence
                auto it = out[j].find(f.second); if (it == out[j].end()) continue;
                bool known = subj[k].count(f.first) > 0;
                for (u32 c : it->second) { if (c == f.first) continue; h.n++; if (known) h.pn++; if (rels[k].stated.count({f.first, c})) h.k++; }
            }
            finish(h);
        }
        if (CHAIN_L >= 3) minePaths(out, subj, finish);
        if (F_COV || F_LABELS) rescoreRules(subj);
        if (F_COND && (F_COV || F_LABELS)) specialize(out, subj, base);
        if (F_TREES) mineTrees();
        if (F_REPL) replicate();
        std::sort(ruleList.begin(), ruleList.end(), [](auto& a, auto& b) { return a.accepted != b.accepted ? a.accepted : a.lift > b.lift; });
    }
    // ── REPLICATE (studies/noise): split the subjects into two halves by a hash of their name. An accepted rule stays accepted
    //    only if, in each half separately, its predictions from stated facts agree with the stated answer at least SUPPORT times
    //    and clearly above chance (z >= 3; for tree rules the same corrected threshold z* used to accept them). ──
    void replicate() {
        std::vector<std::set<std::pair<u32, u32>>> cap(ruleList.size());
        capture = &cap; inferCore(1); capture = nullptr;
        for (auto& R : rels) { R.derived.clear(); R.lawDerived.clear(); }
        conflicts.clear(); staleAlt.clear();
        auto half = [&](u32 a) {   // FNV-1a of the name, then a 64-bit finalizer so similar names (n12, n13) spread evenly
            u64 h = 1469598103934665603ull; for (unsigned char ch : voc.str[a]) { h ^= ch; h *= 1099511628211ull; }
            h ^= h >> 33; h *= 0xff51afd7ed558ccdull; h ^= h >> 33; h *= 0xc4ceb9fe1a85ec53ull; h ^= h >> 33;
            return int(h & 1); };
        std::vector<std::set<u32>> subj(rels.size());
        for (size_t i = 0; i < rels.size(); ++i) for (auto& f : rels[i].stated) subj[i].insert(f.first);
        for (size_t i = 0; i < ruleList.size(); ++i) {
            auto& h = ruleList[i]; if (!h.accepted) continue;
            auto& R = rels[h.r3]; double base;
            if (h.type == 'G') { size_t c = 0; for (auto& f : R.stated) if (f.second == h.headVal) ++c; base = double(c) / double(std::max<size_t>(1, subj[h.r3].size())); }
            else { std::set<u32> o; for (auto& f : R.stated) o.insert(f.second); base = double(R.stated.size()) / double(std::max<size_t>(1, subj[h.r3].size() * o.size())); }
            u64 n[2] = {0, 0}, k[2] = {0, 0}, pn[2] = {0, 0};
            for (auto& p : cap[i]) { int s = half(p.first); n[s]++; if (subj[h.r3].count(p.first)) pn[s]++; if (R.stated.count(p)) k[s]++; }
            double zreq = h.type == 'G' ? treeZ : 3.0; bool ok = true; std::string why;
            for (int s = 0; s < 2; ++s) {
                double ex = double(pn[s]) * base, sd = std::sqrt(std::max(1e-9, ex * (1 - base))), z = (double(k[s]) - ex) / sd;
                char buf[112]; std::snprintf(buf, sizeof buf, "%shalf %c: %llu of %llu known agree, z=%.1f", s ? "; " : "", 'A' + s, (unsigned long long)k[s], (unsigned long long)pn[s], z);
                why += buf; if (k[s] < K_MIN || z < zreq) ok = false;
            }
            if (!ok) { h.accepted = false; h.repl = "did not replicate (" + why + ")"; ++replRejected; }
        }
    }
    // ── multi-premise study: path rules R1 & ... & Rl => T, 3 <= l <= CHAIN_L, proposed only from paths that connect stated T pairs ──
    template <class Fin>
    void minePaths(const std::vector<std::map<u32, std::vector<u32>>>& out, const std::vector<std::set<u32>>& subj, Fin& finish) {
        size_t m = rels.size();
        std::map<u32, std::vector<std::pair<int, u32>>> adj;
        for (size_t r = 0; r < m; ++r) for (auto& f : rels[r].stated) adj[f.first].push_back({(int)r, f.second});
        std::map<std::pair<u32, u32>, std::vector<int>> pairT;
        for (size_t t = 0; t < m; ++t) for (auto& f : rels[t].stated) pairT[f].push_back((int)t);
        std::set<u32> starts; for (auto& kv : pairT) starts.insert(kv.first.first);
        std::vector<std::map<std::vector<int>, u64>> sup(m);
        std::vector<int> seq;
        for (u32 a : starts) {
            u64 steps = 0; std::vector<u32> onPath{a};
            std::function<void(u32, int)> dfs = [&](u32 x, int d) {
                auto it = adj.find(x); if (it == adj.end()) return;
                for (auto& e : it->second) {
                    if (++steps > 50000) return;
                    if (std::find(onPath.begin(), onPath.end(), e.second) != onPath.end()) continue;   // simple paths only
                    seq.push_back(e.first); onPath.push_back(e.second); int l = d + 1;
                    if (l >= 3) { auto pt = pairT.find({a, e.second}); if (pt != pairT.end()) for (int t : pt->second) sup[t][seq]++; }
                    if (l < CHAIN_L) dfs(e.second, l);
                    seq.pop_back(); onPath.pop_back();
                }
            };
            dfs(a, 0);
        }
        for (size_t t = 0; t < m; ++t) {
            std::vector<std::pair<u64, std::vector<int>>> cand;
            for (auto& kv : sup[t]) if (kv.second >= K_MIN) cand.push_back({kv.second, kv.first});
            std::sort(cand.begin(), cand.end(), [](auto& x, auto& y) { return x.first != y.first ? x.first > y.first : x.second < y.second; });
            if (cand.size() > 200) cand.resize(200);
            for (auto& c : cand) {
                RuleH h{'P', c.second[0], -1, (int)t}; h.path = c.second;
                std::set<u32> s0; for (auto& f : rels[h.path[0]].stated) s0.insert(f.first);
                for (u32 x0 : s0) {
                    if (F_STALE && touched.count(x0)) continue;
                    std::set<u32> ends; std::vector<u32> onPath{x0}; u64 steps = 0;
                    std::function<void(size_t, u32)> walk = [&](size_t i, u32 x) {
                        if (i == h.path.size()) { ends.insert(x); return; }
                        auto it = out[h.path[i]].find(x); if (it == out[h.path[i]].end()) return;
                        for (u32 y : it->second) {
                            if (++steps > 50000) return;
                            if (std::find(onPath.begin(), onPath.end(), y) != onPath.end()) continue;
                            onPath.push_back(y); walk(i + 1, y); onPath.pop_back();
                        }
                    };
                    walk(0, x0);
                    bool known = subj[t].count(x0) > 0;
                    for (u32 e : ends) { h.n++; if (known) h.pn++; if (rels[t].stated.count({x0, e})) h.k++; }
                }
                finish(h);
            }
        }
    }
    // ── tree-shaped rules (studies/trees): A(x,g) & branch(g)... => T(x,c), proposed from features of subjects that hold T(x,c) ──
    void mineTrees() {
        size_t m = rels.size();
        std::vector<std::map<u32, std::vector<u32>>> fwd(m), bwd(m);
        for (size_t r = 0; r < m; ++r) for (auto& f : rels[r].stated) { fwd[r][f.first].push_back(f.second); bwd[r][f.second].push_back(f.first); }
        auto stated = [&](int r, u32 a, u32 b) { return rels[r].stated.count({a, b}) > 0; };
        // Branch features of anchor g, never using x itself. Performance (studies/trees DEVIATIONS D1): the raw features of
        // each g are computed once and cached with the entities they pass through, then filtered for x; same results as
        // recomputing them per (g, x), including the 2,000-feature cap, which is applied in the same order.
        struct RawF { TBranch b; u32 via; };   // via = the entity the branch passes through (y), or the leaf constant
        std::map<u32, std::vector<RawF>> rawCache;
        auto raw = [&](u32 g) -> const std::vector<RawF>& {
            auto it = rawCache.find(g); if (it != rawCache.end()) return it->second;
            std::vector<RawF> out;
            for (size_t r = 0; r < m; ++r) {
                auto jt = fwd[r].find(g); if (jt == fwd[r].end()) continue;
                for (u32 y : jt->second) {
                    if (y == g) continue;
                    out.push_back({{(int)r, -1, y}, y});
                    for (size_t s2 = 0; s2 < m; ++s2) {
                        auto kt = fwd[s2].find(y); if (kt == fwd[s2].end()) continue;
                        for (u32 k : kt->second) if (k != g && k != y) out.push_back({{(int)r, (int)s2, k}, y});
                    }
                }
            }
            return rawCache[g] = std::move(out);
        };
        auto feats = [&](u32 g, u32 x) {
            std::vector<TBranch> out;
            for (auto& f : raw(g)) {   // the original loop order, so the cap keeps the same features
                if (out.size() >= 2000) break;
                if (f.via == x || f.b.k == x) continue;
                out.push_back(f.b);
            }
            std::sort(out.begin(), out.end()); out.erase(std::unique(out.begin(), out.end()), out.end());
            return out;
        };
        auto holds = [&](u32 g, u32 x, const TBranch& b) {
            if (b.k == x) return false;
            if (b.s < 0) return b.k != g && stated(b.r, g, b.k);
            auto it = fwd[b.r].find(g); if (it == fwd[b.r].end()) return false;
            for (u32 y : it->second) if (y != x && y != g && y != b.k && stated(b.s, y, b.k)) return true;
            return false;
        };
        struct Cand { int t; u32 c; int a; bool inv; std::vector<TBranch> br; u64 sup; };
        std::vector<Cand> cands; double tStart = nowms();
        for (size_t t = 0; t < m; ++t) {
            std::map<u32, std::set<u32>> vals; for (auto& f : rels[t].stated) vals[f.first].insert(f.second);
            std::set<u32> objs; size_t single = 0; for (auto& v : vals) { if (v.second.size() == 1) ++single; objs.insert(v.second.begin(), v.second.end()); }
            if (vals.empty() || double(single) / vals.size() < 0.95 || objs.size() > 8) continue;   // value-like targets only
            for (u32 c : objs) {
                std::vector<u32> pos; for (auto& v : vals) if (v.second.count(c)) pos.push_back(v.first);
                if (pos.size() < K_MIN) continue;
                // Feature ids for this (T, c): id <-> (anchor relation, direction, branch). Same candidates and supports as
                // the original set-based search (studies/trees DEVIATIONS D1), computed with integer keys.
                std::map<std::tuple<int, bool, TBranch>, int> fid; std::vector<std::tuple<int, bool, TBranch>> fkey;
                auto idOf = [&](int a, bool inv, const TBranch& b) { auto k = std::make_tuple(a, inv, b); auto it = fid.find(k);
                    if (it != fid.end()) { return it->second; } int id = (int)fkey.size(); fid.emplace(k, id); fkey.push_back(k); return id; };
                // per positive subject: its anchors' features, in the original order (anchor relation, direction, g, sorted branches)
                std::vector<std::vector<std::vector<int>>> perX(pos.size());
                for (size_t xi = 0; xi < pos.size(); ++xi) {
                    u32 x = pos[xi];
                    for (size_t a = 0; a < m; ++a) {
                        if (a == t) continue;
                        for (int inv = 0; inv < 2; ++inv) {
                            auto& M = inv ? bwd[a] : fwd[a]; auto it = M.find(x); if (it == M.end()) continue;
                            for (u32 g : it->second) {
                                if (g == x) continue;
                                std::vector<int> ids; for (auto& f : feats(g, x)) ids.push_back(idOf((int)a, (bool)inv, f));
                                perX[xi].push_back(std::move(ids));
                            }
                        }
                    }
                }
                std::vector<u64> sup1(fkey.size(), 0);
                for (auto& anchors : perX) { std::vector<int> u; for (auto& ids : anchors) u.insert(u.end(), ids.begin(), ids.end());
                    std::sort(u.begin(), u.end()); u.erase(std::unique(u.begin(), u.end()), u.end()); for (int id : u) sup1[id]++; }
                std::vector<char> inF1(fkey.size()); for (size_t id = 0; id < fkey.size(); ++id) inF1[id] = sup1[id] >= K_MIN;
                auto f1Of = [&](const std::vector<int>& ids) { std::vector<int> f; for (int id : ids) if (inF1[id]) f.push_back(id); if (f.size() > 40) f.resize(40); return f; };
                std::unordered_map<u64, u64> sup2h;   // (id1 << 32 | id2) -> subjects
                for (auto& anchors : perX) {
                    std::vector<std::pair<int, int>> u;
                    for (auto& ids : anchors) { auto f = f1Of(ids); for (size_t i = 0; i < f.size(); ++i) for (size_t j = i + 1; j < f.size(); ++j) u.push_back({f[i], f[j]}); }
                    std::sort(u.begin(), u.end()); u.erase(std::unique(u.begin(), u.end()), u.end()); for (auto& pr : u) sup2h[(u64(pr.first) << 32) | u64(pr.second)]++;
                }
                std::map<std::pair<int, int>, u64> sup2; for (auto& kv : sup2h) sup2[{int(kv.first >> 32), int(kv.first & 0xFFFFFFFFu)}] = kv.second;
                auto pairOK = [&](int p, int q) { auto it = sup2h.find((u64(p) << 32) | u64(q)); return it != sup2h.end() && it->second >= K_MIN; };
                std::map<std::array<int, 3>, u64> sup3;
                for (auto& anchors : perX) {
                    std::vector<std::array<int, 3>> u;
                    for (auto& ids : anchors) { auto f = f1Of(ids);
                        for (size_t i = 0; i < f.size(); ++i) for (size_t j = i + 1; j < f.size(); ++j) { if (!pairOK(f[i], f[j])) continue;
                            for (size_t l = j + 1; l < f.size(); ++l) if (pairOK(f[i], f[l]) && pairOK(f[j], f[l])) u.push_back({f[i], f[j], f[l]}); } }
                    std::sort(u.begin(), u.end()); u.erase(std::unique(u.begin(), u.end()), u.end()); for (auto& tr : u) sup3[tr]++;
                }
                // rebuild the original candidate order: level 1, 2, 3, each in (anchor, direction, branches) order
                using Key = std::tuple<int, bool, std::vector<TBranch>>;
                auto keyOf = [&](std::initializer_list<int> ids) { Key k; bool first = true;
                    for (int id : ids) { auto& fk = fkey[id]; if (first) { std::get<0>(k) = std::get<0>(fk); std::get<1>(k) = std::get<1>(fk); first = false; }
                        std::get<2>(k).push_back(std::get<2>(fk)); } return k; };
                std::vector<std::pair<Key, u64>> L1, L2, L3;
                for (size_t id = 0; id < fkey.size(); ++id) if (sup1[id] >= K_MIN) L1.push_back({keyOf({(int)id}), sup1[id]});
                for (auto& kv : sup2) if (kv.second >= K_MIN) L2.push_back({keyOf({kv.first.first, kv.first.second}), kv.second});
                for (auto& kv : sup3) if (kv.second >= K_MIN) L3.push_back({keyOf({kv.first[0], kv.first[1], kv.first[2]}), kv.second});
                for (auto* Lv : {&L1, &L2, &L3}) std::sort(Lv->begin(), Lv->end(), [](auto& p, auto& q) { return p.first < q.first; });
                std::vector<Cand> local;
                for (auto* Lv : {&L1, &L2, &L3}) for (auto& kv : *Lv) local.push_back({(int)t, c, std::get<0>(kv.first), std::get<1>(kv.first), std::get<2>(kv.first), kv.second});
                std::sort(local.begin(), local.end(), [](const Cand& p, const Cand& q) { return p.sup != q.sup ? p.sup > q.sup : p.br.size() < q.br.size(); });
                if (local.size() > 300) local.resize(300);
                cands.insert(cands.end(), local.begin(), local.end());
            }
        }
        if (cands.empty()) return;
        double tGen = nowms();
        // statistics of a tree over every subject whose anchor matches all branches
        std::map<std::tuple<int, u32, int, bool, std::vector<TBranch>>, std::array<double, 3>> memo;
        auto stats = [&](int t, u32 c, int a, bool inv, const std::vector<TBranch>& br) {
            auto key = std::make_tuple(t, c, a, inv, br); auto it = memo.find(key); if (it != memo.end()) return it->second;
            std::set<u32> X; auto& G = inv ? fwd[a] : bwd[a];   // g -> subjects x
            for (auto& gx : G) for (u32 x : gx.second) {
                if (x == gx.first) { continue; } bool ok = true;
                for (auto& b : br) if (!holds(gx.first, x, b)) { ok = false; break; }
                if (ok) X.insert(x);
            }
            std::map<u32, std::set<u32>> known; for (auto& f : rels[t].stated) known[f.first].insert(f.second);
            double n = X.size(), k = 0, pn = 0;
            for (u32 x : X) { auto kt = known.find(x); if (kt != known.end()) { ++pn; if (kt->second.count(c)) ++k; } }
            return memo[key] = {n, k, pn};
        };
        double Mc = (double)cands.size(), p = 0.00135 / Mc, lo = 0, hi = 40;
        for (int i = 0; i < 200; ++i) { double mid = (lo + hi) / 2; if (0.5 * std::erfc(mid / std::sqrt(2.0)) > p) lo = mid; else hi = mid; }
        double zstar = std::max(3.0, hi);
        std::vector<RuleH> accepted, rejected;
        for (auto& cd : cands) {
            auto st = stats(cd.t, cd.c, cd.a, cd.inv, cd.br);
            double n = st[0], k = st[1], pn = st[2];
            std::map<u32, std::set<u32>> known; for (auto& f : rels[cd.t].stated) known[f.first].insert(f.second);
            double kc = 0; for (auto& kv : known) if (kv.second.count(cd.c)) ++kc;
            double bc = known.empty() ? 0 : kc / known.size();
            RuleH h{'G', cd.a, -1, cd.t}; h.anchorInv = cd.inv; h.headVal = cd.c; h.branches = cd.br;
            h.n = (u64)n; h.k = (u64)k; h.pn = (u64)pn; h.rate = n > 0 ? k / n : 0; h.base = bc; h.lift = bc > 0 ? h.rate / bc : 0;
            h.pca = pn > 0 ? k / pn : 0; h.cov = -1; h.rel = h.pca; h.law = h.rel >= LAW_MIN;
            double sd = std::sqrt(std::max(1e-9, pn * bc * (1 - bc))), z = (k - pn * bc) / sd;
            bool ok = k >= K_MIN && pn >= 5 && h.pca >= PCA_MIN && z >= zstar;
            for (size_t d = 0; ok && d < cd.br.size(); ++d) {   // branch economy: every branch must raise agreement by >= 0.10
                std::vector<TBranch> sub; for (size_t e = 0; e < cd.br.size(); ++e) if (e != d) sub.push_back(cd.br[e]);
                auto ss = stats(cd.t, cd.c, cd.a, cd.inv, sub);
                double subAgree = ss[2] > 0 ? ss[1] / ss[2] : 0;
                if (h.pca - subAgree < 0.10) ok = false;
            }
            h.accepted = ok;
            (ok ? accepted : rejected).push_back(h);
        }
        if (F_PROFILE) std::printf("[PROFILE] trees: %zu candidates, z* %.2f | candidate search %.1f ms | scoring %.1f ms\n", cands.size(), zstar, tGen - tStart, nowms() - tGen);
        std::sort(rejected.begin(), rejected.end(), [](auto& x, auto& y) { return x.pca > y.pca; });
        if (rejected.size() > 20) rejected.resize(20);
        ruleList.insert(ruleList.end(), accepted.begin(), accepted.end());
        ruleList.insert(ruleList.end(), rejected.begin(), rejected.end());
        treeCandidates = (u64)cands.size(); treeZ = zstar;
    }
    u64 treeCandidates = 0; double treeZ = 0;
    // the shipped acceptance test and reliability label, for a rule whose statistics were recomputed
    bool passes(RuleH& x, const std::vector<bool>& functional) {
        double cR = (x.r3 < (int)covRel.size() && covRel[x.r3] > 0) ? covRel[x.r3] : covGlobal; x.cov = cR;
        double bar = (F_COV && cR > 0) ? std::min(RATE_MIN, RATE_REL * cR) : RATE_MIN;
        bool classic = x.lift >= LIFT_MIN && x.rate >= bar;
        double ex = double(x.pn) * x.base, sd = std::sqrt(std::max(1e-9, ex * (1 - x.base)));
        bool pcaOk = x.pn >= 5 && x.pca >= PCA_MIN && (double(x.k) - ex) / sd >= 3.0;
        x.accepted = x.k >= K_MIN && (classic || pcaOk);
        x.rel = functional[x.r3] ? x.pca : (cR > 0 ? std::min(1.0, x.rate / cR) : x.rate);
        x.law = x.rel >= LAW_MIN;
        return x.accepted;
    }
    // ── multi-premise study: a condition restricts an accepted rule to the group where its conclusions are actually observed ──
    void specialize(const std::vector<std::map<u32, std::vector<u32>>>& out, const std::vector<std::set<u32>>& subj, const std::vector<double>& base) {
        size_t m = rels.size();
        std::vector<std::map<u32, std::set<u32>>> vals(m);
        for (size_t q = 0; q < m; ++q) for (auto& f : rels[q].stated) vals[q][f.first].insert(f.second);
        std::vector<bool> functional(m);
        for (size_t i = 0; i < m; ++i) { size_t single = 0; for (auto& x : vals[i]) if (x.second.size() == 1) ++single; functional[i] = !vals[i].empty() && double(single) / double(vals[i].size()) >= 0.95; }
        for (auto& h : ruleList) {
            if (!h.accepted || h.type == 'P' || h.type == 'G') continue;
            std::map<u32, std::pair<u64, u64>> cs;   // head subject -> (chains, conclusions stated)
            if (h.type == 'I') {
                for (auto& f : rels[h.r1].stated) { if (f.first == f.second) continue; if (F_STALE && (touched.count(f.first) || touched.count(f.second))) continue;
                    auto& x = cs[f.second]; x.first++; if (rels[h.r3].stated.count({f.second, f.first})) x.second++; }
            } else {
                for (auto& f : rels[h.r1].stated) { if (F_STALE && touched.count(f.first)) continue;
                    auto it = out[h.r2].find(f.second); if (it == out[h.r2].end()) continue;
                    for (u32 c : it->second) { if (c == f.first) continue; auto& x = cs[f.first]; x.first++; if (rels[h.r3].stated.count({f.first, c})) x.second++; } }
            }
            if (cs.size() < 10) continue;
            double bestZ = 0; RuleH best = h; bool found = false;
            for (size_t q = 0; q < m; ++q) {
                if ((int)q == h.r3) continue;
                std::map<u32, std::pair<double, double>> g;   // value -> (subjects, subjects whose answer in T is known)
                for (auto& sc : cs) { auto it = vals[q].find(sc.first); if (it == vals[q].end()) continue; bool kn = subj[h.r3].count(sc.first) > 0;
                    for (u32 v : it->second) { g[v].first++; if (kn) g[v].second++; } }
                double bs = 0; for (auto& x : g) if (x.second.first >= 5) bs = std::max(bs, x.second.second / x.second.first);
                if (bs <= 0) continue;
                std::set<u32> K; for (auto& x : g) if (x.second.first >= 5 && x.second.second / x.second.first >= bs / 2) K.insert(x.first);
                size_t eligible = 0; for (auto& x : g) if (x.second.first >= 5) ++eligible;
                if (2 * K.size() > eligible) continue;                 // R2-F2(ii): a condition names at most half of the eligible values
                double nI = 0, kI = 0, pnI = 0, nO = 0, kO = 0, sI = 0, knI = 0, sO = 0, knO = 0;
                for (auto& sc : cs) {
                    auto it = vals[q].find(sc.first); if (it == vals[q].end()) continue;   // R2-F2(i): value unknown = neither inside nor outside
                    bool in = false; for (u32 v : it->second) if (K.count(v)) in = true;
                    bool kn = subj[h.r3].count(sc.first) > 0;
                    if (in) { nI += sc.second.first; kI += sc.second.second; if (kn) pnI += sc.second.first; sI++; if (kn) knI++; }
                    else { nO += sc.second.first; kO += sc.second.second; sO++; if (kn) knO++; }
                }
                if (sI < 5 || sO < 5 || nI == 0 || nO == 0) continue;
                double pin = knI / sI, pout = knO / sO, pp = (knI + knO) / (sI + sO);
                double z = (pp > 0 && pp < 1) ? (pin - pout) / std::sqrt(pp * (1 - pp) * (1 / sI + 1 / sO)) : 0;
                if (!(pin >= 3 * pout && z >= 3)) continue;            // (b) expected evidence is missing outside the group
                if (!(kO / nO <= 0.1 * (kI / nI))) continue;           // (c) the rule's conclusions are (almost) never stated outside it
                RuleH hi = h; hi.n = (u64)nI; hi.k = (u64)kI; hi.pn = (u64)pnI; hi.rate = kI / nI; hi.base = base[h.r3];
                hi.lift = hi.base > 0 ? hi.rate / hi.base : 0; hi.pca = pnI > 0 ? kI / pnI : 0;
                if (!passes(hi, functional)) continue;                 // (a) inside the group the rule passes the shipped test
                if (z > bestZ) { bestZ = z; hi.condRel = (int)q; hi.condVals = K; best = hi; found = true; }
            }
            if (found) {
                best.condSubj.clear();
                for (auto& sv : vals[best.condRel]) for (u32 v : sv.second) if (best.condVals.count(v)) best.condSubj.insert(sv.first);
                h = best;
            }
        }
    }
    // completeness estimate from inverse/symmetric redundancy; coverage-aware acceptance; reliability labels
    void rescoreRules(const std::vector<std::set<u32>>& subj) {
        size_t m = rels.size();
        covRel.assign(m, -1);
        for (auto& h : ruleList) if (h.type == 'I' && h.lift >= 20 && h.k >= 10) covRel[h.r3] = std::max(covRel[h.r3], h.rate);
        std::vector<double> v; for (double c : covRel) if (c > 0) v.push_back(c);
        std::sort(v.begin(), v.end()); covGlobal = v.empty() ? -1 : v[v.size() / 2];
        std::vector<bool> functional(m);
        for (size_t i = 0; i < m; ++i) {
            std::map<u32, int> c; for (auto& f : rels[i].stated) c[f.first]++;
            size_t single = 0; for (auto& x : c) if (x.second == 1) ++single;
            functional[i] = !c.empty() && double(single) / double(c.size()) >= 0.95;
        }
        for (auto& h : ruleList) {
            if (h.type == 'G') continue;   // tree rules keep their own scoring (studies/trees)
            double cR = covRel[h.r3] > 0 ? covRel[h.r3] : covGlobal; h.cov = cR;
            double bar = (F_COV && cR > 0 && h.type != 'P') ? std::min(RATE_MIN, RATE_REL * cR) : RATE_MIN;   // relax for sparse data, never tighten (R2-F1: not for path rules)
            bool classic = h.lift >= LIFT_MIN && h.rate >= bar;
            double ex = double(h.pn) * h.base, sd = std::sqrt(std::max(1e-9, ex * (1 - h.base)));
            bool pcaOk = h.pn >= 5 && h.pca >= PCA_MIN && (double(h.k) - ex) / sd >= 3.0;
            h.accepted = h.k >= K_MIN && (classic || pcaOk);
            h.rel = functional[h.r3] ? h.pca : ((cR > 0 && h.type != 'P') ? std::min(1.0, h.rate / cR) : h.rate);   // R2-F1
            h.law = h.rel >= LAW_MIN;
        }
        (void)subj;
    }
    std::string ruleText(const RuleH& h) const {
        auto nm = [&](int r) { return "[" + words(rels[r].tmpl) + "]"; };
        std::string cond;
        if (h.condRel >= 0) {
            std::string vs; for (u32 v : h.condVals) { if (!vs.empty()) vs += "|"; vs += voc.str[v]; }
            cond = " if " + nm(h.condRel) + "(" + (h.type == 'I' ? "b" : "a") + "," + vs + ")";
        }
        if (h.type == 'G') {
            std::string t = "TREE " + nm(h.r1) + (h.anchorInv ? "(g,a)" : "(a,g)"); int yi = 0;
            for (auto& b : h.branches) {
                if (b.s < 0) t += " & " + nm(b.r) + "(g," + voc.str[b.k] + ")";
                else { std::string y = "y" + std::to_string(++yi); t += " & " + nm(b.r) + "(g," + y + ") & " + nm(b.s) + "(" + y + "," + voc.str[b.k] + ")"; }
            }
            return t + " => " + nm(h.r3) + "(a," + voc.str[h.headVal] + ")";
        }
        if (h.type == 'I') return nm(h.r1) + "(a,b) => " + nm(h.r3) + "(b,a)" + cond;
        if (h.type == 'P') {
            static const char* var = "abcdefghijk"; std::string t;
            for (size_t i = 0; i < h.path.size(); ++i) { if (i) t += " & "; t += nm(h.path[i]) + "(" + var[i] + "," + var[i + 1] + ")"; }
            return t + " => " + nm(h.r3) + "(a," + var[h.path.size()] + ")" + cond;
        }
        return nm(h.r1) + "(a,b) & " + nm(h.r2) + "(b,c) => " + nm(h.r3) + "(a,c)" + cond;
    }

    // deduction to a fixpoint: every derived fact carries its proof
    void computeDeps() {
        depFacts.clear(); depRule.clear(); depSubj.clear();
        auto all = [&](int r) { std::vector<std::pair<u32, u32>> v(rels[r].stated.begin(), rels[r].stated.end()); for (auto& d : rels[r].derived) v.push_back(d.first); return v; };
        for (auto& sf : supFacts) {
            int ri = std::get<0>(sf); u32 x = std::get<1>(sf), o = std::get<2>(sf); int idx = std::get<3>(sf);
            std::vector<std::tuple<int, u32, u32, std::string>> cand;
            for (auto& h : ruleList) {
                if (!h.accepted || h.type == 'P' || h.type == 'G') continue;
                if (h.type == 'I') { if (h.r1 == ri) cand.emplace_back(h.r3, o, x, ruleText(h)); continue; }
                if (h.r1 == ri) for (auto& f : all(h.r2)) if (f.first == o && f.second != x) cand.emplace_back(h.r3, x, f.second, ruleText(h));
                if (h.r2 == ri) for (auto& f : all(h.r1)) if (f.second == x && f.first != o) cand.emplace_back(h.r3, f.first, o, ruleText(h));
            }
            for (auto& t : cand) {
                int r3 = std::get<0>(t); u32 a = std::get<1>(t), b = std::get<2>(t);
                if (!rels[r3].stated.count({a, b})) continue;
                auto key = renderFact(rels[r3], a, b);
                if (depFacts.emplace(key, idx).second) { depRule[key] = std::get<3>(t); depSubj.insert(a); depSubj.insert(b); }
            }
        }
    }
    void infer(int maxDepth = 4) {
        depFacts.clear(); depRule.clear(); depSubj.clear();
        inferCore(maxDepth);
        if (!supFacts.empty()) { computeDeps(); inferCore(maxDepth); }
        for (size_t i = 0; i < rels.size(); ++i) {   // contradictions and undetermined order are reported, not resolved
            for (auto& c : rels[i].contradicted) conflicts.emplace_back((int)i, c.first, 0u, 0u, "CONTRADICTION: " + c.second);
            for (auto& c : rels[i].unknownSubj) conflicts.emplace_back((int)i, c.first, 0u, 0u, "CURRENT UNKNOWN: " + c.second);
            for (auto& c : rels[i].disagree) conflicts.emplace_back((int)i, c.first, 0u, 0u, "SOURCES DISAGREE: " + c.second);
            for (auto& c : rels[i].uncertain) conflicts.emplace_back((int)i, c.first, 0u, 0u, "UNCERTAIN: " + c.second);
        }
        for (auto& q : quarList) conflicts.push_back(q);   // QUARANTINE: facts kept out of the evidence stay reported
        for (auto& q : voteList) conflicts.push_back(q);   // VOTE: so do outvoted facts
    }
    // ── QUARANTINE (studies/noise): a stated fact that two distinct rules contradict (a CONFLICT) is kept out of the evidence:
    //    rules are mined again and inference runs without it. It is never deleted; it is reported as a QUARANTINED conflict. ──
    void quarantine() {
        quarList.clear(); for (auto& R : rels) R.quarantined.clear();
        infer(DEPTH > 0 ? DEPTH : 1000000);
        std::vector<std::tuple<int, u32, u32, u32, std::string>> q;
        for (auto& c : conflicts) {
            int ri = std::get<0>(c); u32 a = std::get<1>(c), s = std::get<2>(c), alt = std::get<3>(c);
            if (!s || !alt || s == alt || staleAlt.count({ri, a}) || !rels[ri].stated.count({a, s})) continue;
            q.push_back(c);
        }
        for (auto& c : q) {
            int ri = std::get<0>(c); u32 a = std::get<1>(c), s = std::get<2>(c);
            rels[ri].stated.erase({a, s});
            rels[ri].quarantined[{a, s}] = "QUARANTINED, not used as evidence: the rules infer \"" + renderFact(rels[ri], a, std::get<3>(c)) + "\" because " + std::get<4>(c);
            quarList.emplace_back(ri, a, s, std::get<3>(c), "QUARANTINED (not used as evidence): " + std::get<4>(c));
        }
        if (!q.empty()) mineRules();
        for (auto& R : rels) { R.derived.clear(); R.lawDerived.clear(); }
        conflicts.clear(); staleAlt.clear();
    }
    void inferCore(int maxDepth) {
        for (auto& R : rels) { R.derived.clear(); R.lawDerived.clear(); R.chain.clear(); }
        conflicts.clear(); staleAlt.clear();
        std::map<std::pair<int, u32>, std::pair<u32, std::string>> pendingUnknown;
        std::vector<bool> functional(rels.size());
        std::vector<std::map<u32, std::set<u32>>> objs(rels.size());
        for (size_t i = 0; i < rels.size(); ++i) {
            for (auto& f : rels[i].stated) objs[i][f.first].insert(f.second);
            size_t single = 0, counted = 0;
            for (auto& o : objs[i]) { if (rels[i].disputed.count(o.first)) continue; ++counted; if (o.second.size() == 1) ++single; }
            functional[i] = counted > 0 && double(single) / double(counted) >= 0.95;
        }
        std::set<std::pair<int, u32>> conflicted;
        auto has = [&](int r, u32 a, u32 b) { return rels[r].stated.count({a, b}) || rels[r].derived.count({a, b}); };
        auto conf = [&](int r, u32 a, u32 b) { if (rels[r].stated.count({a, b})) return 1.0; return rels[r].derived.at({a, b}).first; };
        lastRounds = 0;
        for (int depth = 0; depth < maxDepth; ++depth) {
            ++lastRounds;
            std::vector<std::tuple<int, u32, u32, double, std::string>> add;
            // functional relations: every derivation path is a vote, including paths that agree with what is stated
            std::map<std::pair<int, u32>, std::map<u32, std::pair<int, std::string>>> votes;
            std::map<std::pair<int, u32>, std::map<u32, int>> lawVotes;   // law-tier paths per value
            std::set<std::tuple<int, u32, u32>> lawAdd;
            bool curLaw = false; int curRule = -1, curTs = 0;   // curTs: tendency-tier steps in the current proof's premises
            std::map<std::pair<int, u32>, std::map<u32, int>> voteTs;   // fewest tendency steps among the paths to each value
            std::map<std::tuple<int, u32, u32>, int> addTs;
            auto tsOf = [&](int r, u32 a, u32 b) { auto it = rels[r].chain.find({a, b}); return it == rels[r].chain.end() ? 0 : it->second.second; };
            std::map<std::pair<int, u32>, std::map<u32, std::set<int>>> ruleVotes;   // distinct rules per value
            auto isLaw = [&](int r, u32 a, u32 b) { return rels[r].stated.count({a, b}) || rels[r].lawDerived.count({a, b}); };
            auto propose = [&](int r3, u32 a, u32 c, double score, std::string why) {
                if (capture && curRule >= 0) (*capture)[curRule].insert({a, c});
                int ts = curTs + ((F_LABELS && curRule >= 0 && ruleList[curRule].law) ? 0 : 1);
                if (F_TSTEPS >= 0 && ts > F_TSTEPS) return;   // TENDENCYSTEPS: this proof rests on too many tendency steps
                if (functional[r3]) { auto& m = voteTs[{r3, a}]; auto it = m.find(c); if (it == m.end() || ts < it->second) m[c] = ts; }
                else { auto k = std::make_tuple(r3, a, c); auto it = addTs.find(k); if (it == addTs.end() || ts < it->second) addTs[k] = ts; }
                if (functional[r3]) { auto& v = votes[{r3, a}][c]; if (v.first++ == 0) v.second = why; if (curLaw) lawVotes[{r3, a}][c]++; ruleVotes[{r3, a}][c].insert(curRule); return; }
                if (!has(r3, a, c)) { add.emplace_back(r3, a, c, score, why); if (curLaw) lawAdd.insert({r3, a, c}); }
            };
            for (auto& h : ruleList) {
                if (!h.accepted) continue;
                curRule = int(&h - &ruleList[0]);
                auto all = [&](int r) { std::vector<std::pair<u32, u32>> v(rels[r].stated.begin(), rels[r].stated.end()); for (auto& d : rels[r].derived) v.push_back(d.first); return v; };
                auto condOK = [&](u32 s) { return h.condRel < 0 || h.condSubj.count(s) > 0; };
                if (h.type == 'G') {
                    std::map<int, std::map<u32, std::vector<u32>>> F;   // current facts (stated and derived) of the relations this tree uses
                    auto need = [&](int r) { if (F.count(r)) return; auto& M = F[r]; for (auto& f : all(r)) M[f.first].push_back(f.second); };
                    need(h.r1); for (auto& b : h.branches) { need(b.r); if (b.s >= 0) need(b.s); }
                    auto has = [&](int r, u32 a, u32 b) { auto it = F[r].find(a); return it != F[r].end() && std::find(it->second.begin(), it->second.end(), b) != it->second.end(); };
                    std::map<u32, std::vector<u32>> G2X;   // anchor g -> subjects x
                    for (auto& ax : F[h.r1]) for (u32 o : ax.second) { if (h.anchorInv) G2X[ax.first].push_back(o); else G2X[o].push_back(ax.first); }
                    for (auto& gx : G2X) {
                        u32 g = gx.first;
                        for (u32 x : gx.second) {
                            if (x == g) continue;
                            std::string why = h.anchorInv ? renderFact(rels[h.r1], g, x) : renderFact(rels[h.r1], x, g);
                            double mc = h.anchorInv ? conf(h.r1, g, x) : conf(h.r1, x, g);
                            bool law = h.anchorInv ? isLaw(h.r1, g, x) : isLaw(h.r1, x, g), ok = true;
                            int tsp = h.anchorInv ? tsOf(h.r1, g, x) : tsOf(h.r1, x, g);
                            for (auto& b : h.branches) {
                                if (b.k == x) { ok = false; break; }
                                if (b.s < 0) { if (b.k == g || !has(b.r, g, b.k)) { ok = false; break; }
                                    why += " + " + renderFact(rels[b.r], g, b.k); mc = std::min(mc, conf(b.r, g, b.k)); law = law && isLaw(b.r, g, b.k); tsp = std::max(tsp, tsOf(b.r, g, b.k)); continue; }
                                bool found = false; auto it = F[b.r].find(g);
                                if (it != F[b.r].end()) for (u32 y : it->second) if (y != x && y != g && y != b.k && has(b.s, y, b.k)) {
                                    why += " + " + renderFact(rels[b.r], g, y) + " + " + renderFact(rels[b.s], y, b.k);
                                    mc = std::min({mc, conf(b.r, g, y), conf(b.s, y, b.k)}); law = law && isLaw(b.r, g, y) && isLaw(b.s, y, b.k); tsp = std::max({tsp, tsOf(b.r, g, y), tsOf(b.s, y, b.k)}); found = true; break; }
                                if (!found) { ok = false; break; }
                            }
                            if (!ok) continue;
                            curLaw = F_LABELS && h.law && law; curTs = tsp;
                            propose(h.r3, x, h.headVal, h.pca * mc, why + "  [rule: " + ruleText(h) + "]");
                        }
                    }
                } else if (h.type == 'P') {
                    size_t L = h.path.size();
                    std::vector<std::map<u32, std::vector<u32>>> adjP(L);
                    for (size_t i = 0; i < L; ++i) for (auto& f : all(h.path[i])) adjP[i][f.first].push_back(f.second);
                    std::vector<u32> nodes;
                    for (auto& s0 : adjP[0]) {
                        u32 x0 = s0.first; if (!condOK(x0)) continue;
                        std::set<u32> done; u64 steps = 0; nodes.assign(1, x0);
                        std::function<void(size_t, u32, double, bool, int)> go = [&](size_t i, u32 x, double mc, bool law, int tsp) {
                            if (i == L) {
                                if (x == x0 || !done.insert(x).second) return;
                                std::string why;
                                for (size_t j = 0; j < L; ++j) { if (j) why += " + "; why += renderFact(rels[h.path[j]], nodes[j], nodes[j + 1]); }
                                curLaw = F_LABELS && h.law && law; curTs = tsp;
                                propose(h.r3, x0, x, std::max(h.rate, h.pca) * mc, why + "  [rule: " + ruleText(h) + "]");
                                return;
                            }
                            auto it = adjP[i].find(x); if (it == adjP[i].end()) return;
                            for (u32 y : it->second) {
                                if (++steps > 10000) return;
                                if (std::find(nodes.begin(), nodes.end(), y) != nodes.end()) continue;   // simple paths only
                                nodes.push_back(y); go(i + 1, y, std::min(mc, conf(h.path[i], x, y)), law && isLaw(h.path[i], x, y), std::max(tsp, tsOf(h.path[i], x, y))); nodes.pop_back();
                            }
                        };
                        go(0, x0, 1.0, true, 0);
                    }
                } else if (h.type == 'I') {
                    for (auto& f : all(h.r1)) if (f.first != f.second && condOK(f.second) && ((curLaw = F_LABELS && h.law && isLaw(h.r1, f.first, f.second)) || true) && ((curTs = tsOf(h.r1, f.first, f.second)) || true))
                        propose(h.r3, f.second, f.first, h.rate * conf(h.r1, f.first, f.second),
                                renderFact(rels[h.r1], f.first, f.second) + "  [rule: " + ruleText(h) + "]");
                } else {
                    std::map<u32, std::vector<u32>> out2; for (auto& f : all(h.r2)) out2[f.first].push_back(f.second);
                    for (auto& f : all(h.r1)) {
                        if (!condOK(f.first)) continue;
                        auto it = out2.find(f.second); if (it == out2.end()) continue;
                        for (u32 c : it->second) if (c != f.first && ((curLaw = F_LABELS && h.law && isLaw(h.r1, f.first, f.second) && isLaw(h.r2, f.second, c)) || true) && ((curTs = std::max(tsOf(h.r1, f.first, f.second), tsOf(h.r2, f.second, c))) || true))
                            propose(h.r3, f.first, c, std::max(h.rate, h.pca) * std::min(conf(h.r1, f.first, f.second), conf(h.r2, f.second, c)),
                                    renderFact(rels[h.r1], f.first, f.second) + " + " + renderFact(rels[h.r2], f.second, c) + "  [rule: " + ruleText(h) + "]");
                    }
                }
            }
            for (auto& g : votes) {   // majority vote per subject
                int ri = g.first.first; u32 a = g.first.second;
                u32 top = 0; int tv = -1, second = 0, total = 0;
                for (auto& c : g.second) { total += c.second.first; if (c.second.first > tv) { second = std::max(second, tv); tv = c.second.first; top = c.first; } else second = std::max(second, c.second.first); }
                auto st = objs[ri].find(a);
                if (st != objs[ri].end()) {   // subject already has a stated value
                    u32 s = *st->second.begin(); int sv = g.second.count(s) ? g.second[s].first : 0;
                    {   // a stated value that followed from a superseded fact: re-derive through the same rule, else unknown
                        int k = isDep(ri, a, s);
                        if (k >= 0) {
                            auto& A = supSrc[k];
                            std::string head = "STALE: it followed from '" + A.oldText + "', which " + A.evid + (A.kind == 'X' ? " corrected" : " changed") + " to '" + A.newText + "'; ";
                            auto dr = depRule.find(renderFact(rels[ri], a, s));
                            u32 alt = s; int av = 0;
                            if (F_SAMEFIX && dr != depRule.end()) {   // the linking rule still derives the stated value from current facts: confirmed
                                auto sv = ruleVotes[{ri, a}].find(s); bool conf = false;
                                if (sv != ruleVotes[{ri, a}].end()) for (int rr : sv->second) if (ruleText(ruleList[rr]) == dr->second) conf = true;
                                if (conf) goto after_stale;
                            }
                            for (auto& c : ruleVotes[{ri, a}]) {
                                if (c.first == s) continue;
                                bool same = false; for (int rr : c.second) if (dr != depRule.end() && ruleText(ruleList[rr]) == dr->second) same = true;
                                if (same && g.second[c.first].first > av) { av = g.second[c.first].first; alt = c.first; }
                            }
                            if (alt == s) { pendingUnknown[{ri, a}] = {s, head + "current value unknown (the rule " + (dr != depRule.end() ? dr->second : std::string("?")) + " has no premise for the new value)"}; continue; }
                            if (conflicted.insert({ri, a}).second) {
                                std::string why = head + "now " + g.second[alt].second;
                                conflicts.emplace_back(ri, a, s, alt, why); staleAlt[{ri, a}] = {alt, why};
                            }
                            continue;
                        }
                    }
                    after_stale:
                    if (F_STALE && touched.count(a)) {   // after an explicit change, one law-tier path suffices
                        auto& lv = lawVotes[{ri, a}]; u32 lt = s; int ltv = 0;
                        for (auto& c : lv) if (c.second > ltv) { ltv = c.second; lt = c.first; }
                        if (lt != s && ltv >= 1 && !(lv.count(s) && lv[s] >= ltv) && conflicted.insert({ri, a}).second) {
                            conflicts.emplace_back(ri, a, s, lt, std::string("POSSIBLY STALE after an update: ") + g.second[lt].second);
                            continue;
                        }
                    }
                    if (F_CORROB) {   // a contradiction needs >= 2 distinct rules agreeing on the alternative
                        auto& rv = ruleVotes[{ri, a}]; top = s; tv = 0;
                        for (auto& c : rv) if ((int)c.second.size() > tv) { tv = (int)c.second.size(); top = c.first; }
                        sv = rv.count(s) ? (int)rv[s].size() : 0;
                    }
                    if (top != s && tv > sv && tv >= 2 && conflicted.insert({ri, a}).second)
                        conflicts.emplace_back(ri, a, s, top, g.second[top].second + "  (" + std::to_string(tv) + " of " + std::to_string(total) + " paths)");
                    continue;
                }
                bool already = false; for (auto& d : rels[ri].derived) if (d.first.first == a) { already = true; break; }
                if (already || tv <= second) continue;
                add.emplace_back(ri, a, top, double(tv) / double(total),
                                 g.second[top].second + "  (" + std::to_string(tv) + " of " + std::to_string(total) + " paths agree)");
                if (F_LABELS) { auto& lv = lawVotes[{ri, a}]; bool ok = lv.count(top) && lv[top] > 0; for (auto& c : lv) if (c.first != top && c.second > 0) ok = false; if (ok) lawAdd.insert({ri, a, top}); }
            }
            if (add.empty()) break;
            for (auto& t : add) {
                auto& D = rels[std::get<0>(t)].derived; auto key = std::make_pair(std::get<1>(t), std::get<2>(t));
                auto it = D.find(key);
                if (it == D.end()) {   // round and tendency steps of the proof that first derived it
                    int ri = std::get<0>(t); int ts = 0;
                    if (functional[ri]) { auto& m = voteTs[{ri, key.first}]; auto f = m.find(key.second); if (f != m.end()) ts = f->second; }
                    else { auto f = addTs.find({ri, key.first, key.second}); if (f != addTs.end()) ts = f->second; }
                    rels[ri].chain[key] = {depth + 1, ts};
                }
                if (it == D.end() || it->second.first < std::get<3>(t)) D[key] = {std::get<3>(t), std::get<4>(t)};
                if (lawAdd.count({std::get<0>(t), std::get<1>(t), std::get<2>(t)})) rels[std::get<0>(t)].lawDerived.insert(key);
            }
        }
        for (auto& pu : pendingUnknown) if (conflicted.insert(pu.first).second) {
            conflicts.emplace_back(pu.first.first, pu.first.second, pu.second.first, pu.second.first, pu.second.second); staleAlt[pu.first] = pu.second;
        }
        inferred = true;
    }
    static double nowms() { return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
    void cacheRules() {
        ruleCache.clear();
        for (auto& h : ruleList) ruleCache.push_back({h, rels[h.r1].tmpl, h.r2 >= 0 ? rels[h.r2].tmpl : std::vector<u32>(), rels[h.r3].tmpl});
    }
    void remapRules() {   // cached rules onto the rebuilt relations; a rule whose relation vanished is dropped
        std::map<std::vector<u32>, int> idx; for (size_t i = 0; i < rels.size(); ++i) idx[rels[i].tmpl] = (int)i;
        ruleList.clear();
        for (auto& c : ruleCache) {
            auto a = idx.find(c.t1), b = c.t2.empty() ? idx.end() : idx.find(c.t2), d = idx.find(c.t3);
            if (a == idx.end() || d == idx.end() || (!c.t2.empty() && b == idx.end())) continue;
            RuleH h = c.h; h.r1 = a->second; h.r2 = c.t2.empty() ? -1 : b->second; h.r3 = d->second; ruleList.push_back(h);
        }
        covRel.assign(rels.size(), -1);
        for (auto& h : ruleList) if (h.type == 'I' && h.lift >= 20 && h.k >= 10) covRel[h.r3] = std::max(covRel[h.r3], h.rate);
        std::vector<double> v; for (double c : covRel) if (c > 0) v.push_back(c);
        std::sort(v.begin(), v.end()); covGlobal = v.empty() ? -1 : v[v.size() / 2];
    }
    void ensureModel() {
        if (!dirty) return;
        bool small = F_REFRESH > 0 && CHAIN_L < 3 && !F_COND && !F_TREES && !F_REPL && !F_QUAR && haveCache && voc.str.size() == vocAtFull && double(recordsIngested - recsAtFull) <= F_REFRESH * double(std::max<u64>(1, recs.size()));
        if (small) {   // evidence changed a little: re-project and rebuild relations, keep the learned classes and rules
            double t0 = nowms(); buildRelations(); remapRules(); ++refreshBuilds;
            if (F_PROFILE) std::printf("[PROFILE] refresh: relations %.1f ms (classes and rules reused)\n", nowms() - t0);
        } else {
            double t0 = nowms(); buildClasses(); double t1 = nowms(); buildRelations(); double t2 = nowms(); mineRules(); if (F_QUAR) quarantine(); else quarList.clear(); double t3 = nowms();
            if (F_PROFILE) std::printf("[PROFILE] classes %.1f ms | relations %.1f ms | rule mining %.1f ms\n", t1 - t0, t2 - t1, t3 - t2);
            cacheRules(); haveCache = true; vocAtFull = voc.str.size(); recsAtFull = recordsIngested; ++fullBuilds;
        }
        dirty = false; inferred = false;
    }
    void ensureInferred() { ensureModel(); if (!inferred) { double t0 = nowms(); infer(DEPTH > 0 ? DEPTH : 1000000); if (F_PROFILE) std::printf("[PROFILE] infer %.1f ms, %d rounds\n", nowms() - t0, lastRounds); } }

    // ── SAVE / LOAD: vocab + grammar + record counts. Counts are rebuilt by replay. ──
    static void wv(std::ostream& o, u64 x) { while (x >= 128) { o.put(char((x & 127) | 128)); x >>= 7; } o.put(char(x)); }
    static u64 rv(std::istream& in) { u64 x = 0; int s = 0; int c; while ((c = in.get()) != EOF) { x |= u64(c & 127) << s; if (!(c & 128)) break; s += 7; } return x; }
    bool save(const std::string& path) {
        std::ofstream o(path, std::ios::binary); if (!o) return false;
        o.write("VTX2", 4);
        wv(o, voc.str.size()); for (auto& s : voc.str) { wv(o, s.size()); o.write(s.data(), s.size()); }
        std::vector<u32> remap(g.rules.size(), 0); u32 nr = 0;
        for (u32 r = 0; r < g.rules.size(); ++r) if (r != g.S && g.rules[r].guard) remap[r] = ++nr;
        auto symCode = [&](const Sym* s) -> u64 { return s->kind == NONTERM ? (u64(remap[s->v]) << 1 | 1) : (u64(s->v) << 1); };
        wv(o, nr);
        for (u32 r = 0; r < g.rules.size(); ++r) if (r != g.S && g.rules[r].guard) {
            u64 len = 0; for (Sym* x = g.first(r); x->kind != GUARD; x = x->n) ++len;
            wv(o, len); for (Sym* x = g.first(r); x->kind != GUARD; x = x->n) wv(o, symCode(x));
        }
        u64 len = 0; for (Sym* x = g.first(g.S); x->kind != GUARD; x = x->n) ++len;
        wv(o, len);
        for (Sym* x = g.first(g.S); x->kind != GUARD; x = x->n) wv(o, x->kind == SEP ? 0 : symCode(x));
        wv(o, recs.size()); for (auto& r : recs) wv(o, r.count);
        return true;
    }
    bool load(const std::string& path) {
        std::ifstream in(path, std::ios::binary); if (!in) return false;
        char mg[4]; in.read(mg, 4); if (std::memcmp(mg, "VTX2", 4)) return false;
        voc.id.clear(); voc.str.clear(); voc.space.clear(); g.clear(); recs.clear(); byText.clear(); wc.clear();
        tokensIngested = recordsIngested = 0;
        u64 nv = rv(in);
        for (u64 i = 0; i < nv; ++i) { u64 l = rv(in); std::string s(l, '\0'); in.read(&s[0], l); voc.get(s); }
        u64 nr = rv(in);
        std::vector<u32> rid(nr + 1); for (u64 i = 1; i <= nr; ++i) rid[i] = g.newRule();
        auto mkFrom = [&](u64 c) { return (c & 1) ? g.mk(NONTERM, rid[c >> 1]) : g.mk(TERM, u32(c >> 1)); };
        for (u64 i = 1; i <= nr; ++i) { u64 l = rv(in); for (u64 j = 0; j < l; ++j) g.insertAfter(g.last(rid[i]), mkFrom(rv(in))); }
        u64 ls = rv(in); std::vector<Sym*> seps;
        for (u64 j = 0; j < ls; ++j) {
            u64 c = rv(in);
            if (c == 0) seps.push_back(g.appendSep((u32)seps.size()));
            else g.insertAfter(g.last(g.S), mkFrom(c));
        }
        g.dig.clear();
        for (u32 r = 0; r < g.rules.size(); ++r) if (g.rules[r].guard)
            for (Sym* x = g.first(r); x->kind != GUARD; x = x->n) if (!Grammar::ign(x) && !Grammar::ign(x->n)) g.dig.emplace(Grammar::key(x), x);
        u64 nrec = rv(in);
        for (u64 i = 0; i < nrec; ++i) recs.push_back({seps[i], rv(in)});
        for (u32 r = 0; r < recs.size(); ++r) {
            auto ids = recIds(r); tokensIngested += ids.size(); recordsIngested += recs[r].count;
            if (!recs[r].count) continue;   // retracted record stays in the grammar as a tombstone
            byText.emplace(ids, r);
            countContent(ids, recs[r].count);  // training is ingesting: replay rebuilds the evidence
        }
        dirty = true; return true;
    }
};

// ─────────────────────────────────────────────
// Diagnostics
// ─────────────────────────────────────────────
static double rssMB() {
#ifndef _WIN32
    std::ifstream f("/proc/self/statm"); long a = 0, b = 0; f >> a >> b; return double(b) * double(sysconf(_SC_PAGESIZE)) / 1048576.0;
#else
    return 0;
#endif
}
struct Invariants { u64 dupDigrams = 0, underusedRules = 0; };
static Invariants checkInvariants(const Grammar& g) {
    Invariants inv; std::map<u64, int> seen;
    for (u32 r = 0; r < g.rules.size(); ++r) if (g.rules[r].guard) {
        if (r != g.S && g.rules[r].refs < 2) inv.underusedRules++;
        for (Sym* x = g.first(r); x->kind != GUARD; x = x->n) {
            if (Grammar::ign(x) || Grammar::ign(x->n)) continue;
            if (x->p && Grammar::same(x->p, x) && Grammar::same(x, x->n)) continue;  // overlapping "aaa" is allowed
            if (++seen[Grammar::key(x)] == 2) inv.dupDigrams++;
        }
    }
    return inv;
}

// ─────────────────────────────────────────────
// Commands
// ─────────────────────────────────────────────
static Vault V;

// ─────────────────────────────────────────────
//  SETTINGS REGISTRY: every setting declared once. SET, CONFIG, SAVE and LOAD all read this table.
//  layer = the layer that owns it; experimental = a study option, off by default;
//  saved = travels with the knowledge base in <file>.cfg (diagnostics are not saved).
// ─────────────────────────────────────────────
struct Setting {
    const char* name; const char* layer; bool experimental, saved; const char* help;
    std::function<double()> get; std::function<void(double)> set; double def = 0;
};
#define VTX_SETTING(NAME, LAYER, EXP, SAVED, HELP, FIELD, TYPE) \
    {NAME, LAYER, EXP, SAVED, HELP, [] { return double(V.FIELD); }, [](double v) { V.FIELD = (TYPE)v; }}
static std::vector<Setting>& settings() {
    static std::vector<Setting> s;
    if (s.empty()) {
        s = {
            VTX_SETTING("MAXWORDS", "statistics", false, true, "categories for this many most frequent words; rarer words are not slots", MAX_WORDS, u64),
            VTX_SETTING("MAXRELATIONS", "statistics", false, true, "relations kept, largest first", MAX_RELS, u64),
            VTX_SETTING("CLASS", "statistics", false, true, "similarity needed to merge words into a category", classThresh, double),
            VTX_SETTING("CLUSTERSTREAM", "statistics", true, true, "build categories without listing every similar pair: same categories and answers, far less memory (1/0) (studies/scaling)", F_CSTREAM, int),
            VTX_SETTING("RATE", "induction", false, true, "minimum share of chains whose conclusion is stated", RATE_MIN, double),
            VTX_SETTING("LIFT", "induction", false, true, "minimum rate over the conclusion's base rate", LIFT_MIN, double),
            VTX_SETTING("SUPPORT", "induction", false, true, "minimum confirming chains for a rule", K_MIN, u64),
            VTX_SETTING("PCA", "induction", false, true, "minimum agreement where the answer is known", PCA_MIN, double),
            VTX_SETTING("LAW", "induction", false, true, "reliability needed for the law tier", LAW_MIN, double),
            VTX_SETTING("COVERAGE", "induction", false, true, "relax the rate bar when data looks sparse (1/0)", F_COV, int),
            VTX_SETTING("LABELS", "induction", false, true, "label rules and facts law or tendency (1/0)", F_LABELS, int),
            {"CHAIN", "induction", true, true, "longest rule body, 2-8 premises (studies/multipremise)",
             [] { return double(V.CHAIN_L); }, [](double v) { V.CHAIN_L = std::max(2, std::min(8, (int)v)); }},
            VTX_SETTING("CONDITIONS", "induction", true, true, "learn group conditions on accepted rules (1/0) (studies/multipremise)", F_COND, int),
            VTX_SETTING("TREES", "induction", true, true, "tree-shaped rules joining several branches at one entity (1/0) (studies/trees)", F_TREES, int),
            VTX_SETTING("REPLICATE", "induction", true, true, "a rule must also hold in each half of its subjects (1/0) (studies/noise)", F_REPL, int),
            VTX_SETTING("TENDENCYSTEPS", "inference", true, true, "most tendency-tier steps one proof may contain, -1 = no limit (studies/tendency)", F_TSTEPS, int),
            VTX_SETTING("DEPTH", "inference", false, true, "inference rounds, 0 = until nothing new (studies/depth)", DEPTH, int),
            VTX_SETTING("CORROBORATE", "inference", false, true, "a contradiction needs two distinct rules (1/0)", F_CORROB, int),
            VTX_SETTING("OBS", "evidence", false, true, "project the observation log (1/0)", F_OBS, int),
            VTX_SETTING("STALE", "evidence", false, true, "staleness checks after updates (1/0)", F_STALE, int),
            VTX_SETTING("CHGREMOVALS", "evidence", false, true, "only removals feed the change signal (1/0)", F_CHG_REMOVALS, int),
            VTX_SETTING("SAMEFIX", "evidence", false, true, "same-rule re-derivation confirms a stale candidate (1/0)", F_SAMEFIX, int),
            VTX_SETTING("VOTE", "evidence", true, true, "a value reported more often than all others outvotes them (1/0) (studies/noise)", F_VOTE, int),
            VTX_SETTING("QUARANTINE", "evidence", true, true, "stated facts two rules contradict stop counting as evidence (1/0) (studies/noise)", F_QUAR, int),
            VTX_SETTING("DX", "evidence", true, true, "explained staleness for observations (1/0)", F_DX, int),
            VTX_SETTING("DECL", "evidence", true, true, "declarative amendment records (1/0) (earlier study)", F_DECL, int),
            VTX_SETTING("DECLMINE", "evidence", true, true, "mine amendment records as facts (1/0) (earlier study)", F_DECL_MINE, int),
            VTX_SETTING("DECLFN", "evidence", true, true, "one-value fix for amendments (1/0) (earlier study)", F_DECLFN, int),
            VTX_SETTING("REFRESH", "build", true, true, "reuse classes and rules for small changes (share of records, 0 = off)", F_REFRESH, double),
            VTX_SETTING("PROFILE", "diagnostics", false, false, "print timings (1/0)", F_PROFILE, int),
        };
        for (auto& x : s) x.def = x.get();   // defaults are whatever the engine starts with
    }
    return s;
}
static Setting* findSetting(std::string k) {
    for (auto& c : k) c = (char)std::toupper((unsigned char)c);
    for (auto& x : settings()) if (k == x.name) return &x;
    return nullptr;
}
static std::string nonDefault(bool experimentalOnly) {
    std::string out; char buf[64];
    for (auto& x : settings()) if (x.saved && x.get() != x.def && (!experimentalOnly || x.experimental)) {
        std::snprintf(buf, sizeof buf, " %s=%g", x.name, x.get()); out += buf;
    }
    return out;
}
static void showConfig() {
    for (auto& x : settings())
        std::printf("[CONFIG] %-12s %-8g (default %g)  %-11s %s%s\n", x.name, x.get(), x.def, x.layer,
                    x.experimental ? "EXPERIMENTAL " : "", x.help);
}
static bool saveConfig(const std::string& path) {
    std::ofstream o(path + ".cfg"); if (!o) return false;
    o << "# voltex settings 1\n";
    char buf[64];
    for (auto& x : settings()) if (x.saved && x.get() != x.def) { std::snprintf(buf, sizeof buf, "%.17g", x.get()); o << x.name << " " << buf << "\n"; }
    return true;
}
static void loadConfig(const std::string& path) {   // no .cfg (saved by 2.2.1 or earlier): settings are left as they are
    std::ifstream in(path + ".cfg"); if (!in) return;
    for (auto& x : settings()) if (x.saved) x.set(x.def);
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ss(line); std::string k; double v; if (!(ss >> k >> v)) continue;
        Setting* st = findSetting(k); if (st && st->saved) st->set(v);
    }
    V.dirty = true;
    std::string nd = nonDefault(false);
    if (!nd.empty()) std::printf("[CONFIG] restored from %s.cfg:%s\n", path.c_str(), nd.c_str());
}

static void metrics() {
    Invariants inv = checkInvariants(V.g);
    std::printf("--- VOLTEX v2 METRICS ---\n");
    std::printf(" Records:          %zu unique / %llu ingested\n", V.recs.size(), (unsigned long long)V.recordsIngested);
    std::printf(" Tokens (unique records): %llu\n", (unsigned long long)V.tokensIngested);
    std::printf(" Vocabulary:       %zu tokens\n", V.voc.str.size());
    std::printf(" Grammar:          %zu rules, %zu symbols  (%.3f symbols per input token)\n", V.g.ruleCount(), V.g.liveSyms,
                V.tokensIngested ? double(V.g.liveSyms) / double(V.tokensIngested) : 0.0);
    std::printf(" Pair map:         %zu entries\n", V.g.dig.size());
    std::printf(" Count tables:     %zu bigrams, %zu trigrams\n", V.wc.big.size(), V.wc.tri.size());
    std::printf(" Invariants:       %llu duplicate pairs, %llu under-used rules\n", (unsigned long long)inv.dupDigrams, (unsigned long long)inv.underusedRules);
    std::printf(" Process RSS:      %.1f MB\n", rssMB());
}

static void audit(const Sym* s, int depth, int maxDepth) {
    for (int i = 0; i < depth; ++i) std::printf("  ");
    if (s->kind == TERM) { std::printf("\"%s\"\n", V.voc.str[s->v].c_str()); return; }
    std::vector<u32> o; V.g.emit(s, o);
    std::printf("R%u (used %u times) = \"%s\"\n", s->v, V.g.rules[s->v].refs, V.render(o).c_str());
    if (depth >= maxDepth) return;
    for (const Sym* x = V.g.first(s->v); x->kind != GUARD; x = x->n) audit(x, depth + 1, maxDepth);
}

static std::vector<u32> queryIds(const std::string& q, std::vector<size_t>& holes) {
    std::vector<u32> out; holes.clear();
    for (auto& t : tokenize(q)) {
        if (t[0] == ' ' || t[0] == '\t') continue;
        if (t == "?") { holes.push_back(out.size()); out.push_back(SLOT); continue; }
        long id = V.voc.find(t); out.push_back(id < 0 ? SLOT - 1 : (u32)id);  // SLOT-1 = unknown word
    }
    return out;
}

static void predict(const std::string& prefix, int topk) {
    V.ensureModel();
    std::vector<size_t> h; auto ids = queryIds(prefix, h);
    u32 a = BOS, b = BOS; for (u32 w : ids) { a = b; b = w; }
    std::vector<std::pair<double, u32>> c;
    for (u32 w = 1; w < V.voc.str.size(); ++w) if (!V.voc.space[w] && (w == EOS || (w < V.wc.uni.size() && V.wc.uni[w]))) c.push_back({V.pMix(w, a, b), w});
    std::sort(c.rbegin(), c.rend());
    for (int i = 0; i < topk && i < (int)c.size(); ++i) {
        bool seen = Counts::get(V.wc.tri, pk3(a, b, c[i].second)) > 0;
        std::printf("  %-20s p=%.4f  %s\n", V.voc.str[c[i].second].c_str(), c[i].first, seen ? "observed" : "inferred via categories");
    }
}

static std::string generateText(const std::string& prefix, unsigned seed);
static void generate(const std::string& prefix, unsigned seed) { std::printf("[GENERATE] %s\n", generateText(prefix, seed).c_str()); }
static std::string generateText(const std::string& prefix, unsigned seed) {
    V.ensureModel();
    std::mt19937 rng(seed);
    std::vector<size_t> h; auto ids = queryIds(prefix, h);
    u32 a = BOS, b = BOS; std::string out = prefix;
    for (u32 w : ids) { a = b; b = w; }
    std::vector<u32> cand; for (u32 w = 1; w < V.voc.str.size(); ++w) if (!V.voc.space[w] && (w == EOS || (w < V.wc.uni.size() && V.wc.uni[w]))) cand.push_back(w);
    for (int step = 0; step < 40; ++step) {
        std::vector<double> ps; for (u32 w : cand) ps.push_back(V.pMix(w, a, b));
        std::discrete_distribution<size_t> d(ps.begin(), ps.end());
        u32 w = cand[d(rng)]; if (w == EOS) break;
        if (!out.empty() && wordChar(V.voc.str[w][0])) out += ' ';
        out += V.voc.str[w]; a = b; b = w;
    }
    return out;
}

static void fillQuery(const std::string& pattern, int topk) {
    V.ensureModel();
    std::vector<size_t> holes; auto ids = queryIds(pattern, holes);
    if (holes.size() != 1) { std::puts("[QUERY] use exactly one ? in the pattern"); return; }
    size_t hpos = holes[0];
    std::vector<std::pair<double, u32>> scored;
    for (u32 w = 2; w < V.voc.str.size(); ++w) {
        if (V.voc.space[w] || w >= V.wc.uni.size() || !V.wc.uni[w]) continue;
        auto f = ids; f[hpos] = w;
        double lp = 0; bool seenAll = true;
        for (size_t i = hpos; i < f.size() && i <= hpos + 2; ++i) {
            u32 a = i >= 2 ? f[i - 2] : BOS, b = i >= 1 ? f[i - 1] : BOS;
            lp += std::log(V.pMix(f[i], a, b));
            if (!Counts::get(V.wc.tri, pk3(a, b, f[i]))) seenAll = false;
        }
        scored.push_back({lp + (seenAll ? 1e-12 : 0), w});
    }
    std::sort(scored.rbegin(), scored.rend());
    double Z = 0; for (auto& s : scored) Z += std::exp(s.first - scored[0].first);
    for (int i = 0; i < topk && i < (int)scored.size(); ++i) {
        u32 w = scored[i].second; auto f = ids; f[hpos] = w;
        bool seen = true;
        for (size_t j = hpos; j < f.size() && j <= hpos + 2; ++j) { u32 a = j >= 2 ? f[j - 2] : BOS, b = j >= 1 ? f[j - 1] : BOS; if (!Counts::get(V.wc.tri, pk3(a, b, f[j]))) seen = false; }
        std::printf("  %-20s p=%.3f  %s\n", V.voc.str[w].c_str(), std::exp(scored[i].first - scored[0].first) / Z, seen ? "observed" : "inferred via categories");
    }
}

static void showClasses() {
    V.ensureModel();
    std::map<u32, std::vector<u32>> m;
    for (u32 w = 2; w < V.cls.size(); ++w) if (V.clsSize[V.cls[w]] >= 2) m[V.cls[w]].push_back(w);
    std::printf("[CLASSES] %zu multi-member categories (threshold %.2f)\n", m.size(), V.classThresh);
    int shown = 0;
    std::vector<std::pair<size_t, u32>> order; for (auto& kv : m) order.push_back({kv.second.size(), kv.first});
    std::sort(order.rbegin(), order.rend());
    for (auto& o : order) {
        if (++shown > 25) break;
        auto& ws = m[o.second];
        std::printf("  C%u (%zu): ", o.second, ws.size());
        for (size_t i = 0; i < ws.size() && i < 14; ++i) std::printf("%s ", V.voc.str[ws[i]].c_str());
        if (ws.size() > 14) std::printf("...");
        std::puts("");
    }
}

static void showRelations() {
    V.ensureModel();
    { std::string ex = nonDefault(true); if (!ex.empty()) std::printf("[CONFIG] experimental settings on:%s\n", ex.c_str()); }
    std::printf("[RELATIONS] %zu two-argument templates\n", V.rels.size());
    if (V.wordsSeen > V.MAX_WORDS)   // capacity limits are reported, never silent
        std::printf("[LIMIT] categories cover the %llu most frequent of %llu words; facts naming rarer words are in no relation (SET MAXWORDS)\n",
                    (unsigned long long)V.MAX_WORDS, (unsigned long long)V.wordsSeen);
    if (V.relsSeen > V.MAX_RELS)
        std::printf("[LIMIT] %llu of %llu relations kept, largest first (SET MAXRELATIONS)\n", (unsigned long long)V.MAX_RELS, (unsigned long long)V.relsSeen);
    for (size_t i = 0; i < V.rels.size() && i < 15; ++i) std::printf("  #%zu  %-30s %zu facts\n", i, V.words(V.rels[i].tmpl).c_str(), V.rels[i].stated.size());
    int shown = 0;
    if (V.F_COV || V.F_LABELS) {
        std::printf("[COVERAGE] estimated observation completeness: global %.2f |", V.covGlobal);
        for (size_t i = 0; i < V.rels.size() && i < V.covRel.size(); ++i) if (V.covRel[i] > 0) std::printf(" [%s] %.2f", V.words(V.rels[i].tmpl).c_str(), V.covRel[i]);
        std::puts("");
    }
    std::printf("[RULES] scored by evidence: chains seen (n), conclusion stated (k), lift over base rate\n");
    for (auto& h : V.ruleList) {
        if (!h.accepted && shown >= 14) break;
        if (!h.accepted && h.lift < 1.5) continue;
        ++shown;
        char extra[96] = "";
        if (V.F_COV || V.F_LABELS) std::snprintf(extra, sizeof extra, " | cov=%.2f rel=%.2f tier=%s", h.cov, h.rel, h.law ? "law" : "tendency");
        std::printf("  %s %-60s n=%llu k=%llu rate=%.2f lift=%.1f | where answer known: %llu, agree=%.2f%s%s%s\n", h.accepted ? "ACCEPT" : "reject", V.ruleText(h).c_str(),
                    (unsigned long long)h.n, (unsigned long long)h.k, h.rate, h.lift, (unsigned long long)h.pn, h.pca, extra, h.repl.empty() ? "" : " | ", h.repl.c_str());
    }
}

static void inferCmd(const std::string& arg) {
    V.ensureInferred();
    size_t total = 0; for (auto& R : V.rels) total += R.derived.size();
    std::printf("[INFER] %zu new facts derived from %zu accepted rules\n", total,
                (size_t)std::count_if(V.ruleList.begin(), V.ruleList.end(), [](auto& h) { return h.accepted; }));
    bool all = arg == "ALL" || arg == "all";
    size_t limit = all ? SIZE_MAX : 10, shown = 0;
    for (auto& R : V.rels) for (auto& d : R.derived) {
        if (shown++ >= limit) return;
        if (all && V.F_LABELS) std::printf("FACT\t%s\t%s\n", V.renderFact(R, d.first.first, d.first.second).c_str(), R.lawDerived.count(d.first) ? "law" : "tendency");
        else if (all) std::printf("FACT\t%s\n", V.renderFact(R, d.first.first, d.first.second).c_str());
        else std::printf("  %-32s %sscore=%.2f  because %s\n", V.renderFact(R, d.first.first, d.first.second).c_str(), !V.F_LABELS ? "" : R.lawDerived.count(d.first) ? "[law] " : "[tendency] ", d.second.first, d.second.second.c_str());
    }
}

static void ask(const std::string& q) {
    V.ensureInferred();
    std::vector<size_t> holes; auto ids = queryIds(q, holes);
    int answers = 0;
    for (auto& R : V.rels) {
        if (R.tmpl.size() != ids.size()) continue;
        std::vector<size_t> slots; bool ok = true;
        for (size_t i = 0; i < ids.size(); ++i) { if (R.tmpl[i] == SLOT) slots.push_back(i); else if (ids[i] != R.tmpl[i]) ok = false; }
        if (!ok || slots.size() != 2) continue;
        u32 qa = ids[slots[0]], qb = ids[slots[1]];
        auto fits = [&](u32 a, u32 b) { return (qa == SLOT || qa == a) && (qb == SLOT || qb == b); };
        int ri = int(&R - &V.rels[0]);
        for (auto& f : R.stated) if (fits(f.first, f.second)) {
            std::string fact = V.renderFact(R, f.first, f.second);
            auto st = V.staleAlt.find({ri, f.first});
            if (st != V.staleAlt.end() && f.second == st->second.first) { std::printf("  %-32s stated, %s\n", fact.c_str(), st->second.second.c_str()); ++answers; continue; }
            if (st != V.staleAlt.end()) {
                std::printf("  %-32s stated, STALE\n", fact.c_str());
                std::printf("  %-32s current, because %s\n", V.renderFact(R, f.first, st->second.first).c_str(), st->second.second.c_str()); answers += 2; continue;
            }
            auto cd = R.contradicted.find(f.first); auto uk = R.unknownSubj.find(f.first); auto ve = R.viaEvent.find(f);
            auto dg = R.disagree.find(f.first); auto un = R.uncertain.find(f.first); auto pv = R.prov.find(f);
            if (dg != R.disagree.end()) std::printf("  %-32s stated, SOURCES DISAGREE: %s\n", fact.c_str(), dg->second.c_str());
            else if (un != R.uncertain.end()) std::printf("  %-32s stated, UNCERTAIN: %s\n", fact.c_str(), un->second.c_str());
            else if (pv != R.prov.end()) std::printf("  %-32s stated (per %s)\n", fact.c_str(), pv->second.c_str());
            else if (cd != R.contradicted.end()) std::printf("  %-32s stated, CONTRADICTED: %s\n", fact.c_str(), cd->second.c_str());
            else if (uk != R.unknownSubj.end()) std::printf("  %-32s stated, CURRENT UNKNOWN: %s\n", fact.c_str(), uk->second.c_str());
            else if (ve != R.viaEvent.end()) std::printf("  %-32s stated (current; set by %s)\n", fact.c_str(), ve->second.c_str());
            else std::printf("  %-32s stated\n", fact.c_str());
            ++answers;
        }
        for (auto& f : R.outvoted) if (fits(f.first.first, f.first.second)) { std::printf("  %-32s stated, %s\n", V.renderFact(R, f.first.first, f.first.second).c_str(), f.second.c_str()); ++answers; }
        for (auto& f : R.quarantined) if (fits(f.first.first, f.first.second)) { std::printf("  %-32s stated, %s\n", V.renderFact(R, f.first.first, f.first.second).c_str(), f.second.c_str()); ++answers; }
        for (auto& f : R.superseded) if (fits(f.first.first, f.first.second)) { std::printf("  %-32s %s\n", V.renderFact(R, f.first.first, f.first.second).c_str(), f.second.c_str()); ++answers; }
        for (auto& h : R.histLines) if (fits(std::get<0>(h), std::get<1>(h))) { std::printf("  %-32s %s\n", V.renderFact(R, std::get<0>(h), std::get<1>(h)).c_str(), std::get<2>(h).c_str()); ++answers; }
        for (auto& f : R.withdrawn) if (fits(f.first.first, f.first.second)) { std::printf("  %-32s %s\n", V.renderFact(R, f.first.first, f.first.second).c_str(), f.second.c_str()); ++answers; }
        for (auto& d : R.derived) if (fits(d.first.first, d.first.second)) {
            std::printf("  %-32s inferred%s (score %.2f) because %s\n", V.renderFact(R, d.first.first, d.first.second).c_str(), !V.F_LABELS ? "" : R.lawDerived.count(d.first) ? " [law]" : " [tendency]", d.second.first, d.second.second.c_str()); ++answers; }
    }
    if (!answers) std::puts("  no stated or inferred answer");
}

static void evalFile(const std::string& path) {
    V.ensureModel();
    std::ifstream f(path); std::string line; double bw = 0, bc = 0, bm = 0; u64 n = 0;
    while (std::getline(f, line)) {
        u32 a = BOS, b = BOS;
        for (auto& t : tokenize(line)) {
            if (t[0] == ' ' || t[0] == '\t') continue;
            long id = V.voc.find(t); u32 w = id < 0 ? SLOT - 1 : (u32)id;
            double pw = id < 0 ? 1e-9 : V.wc.p(w, a, b), pc = id < 0 ? 1e-9 : V.pClass(w, a, b);
            bw -= std::log2(pw); bc -= std::log2(pc); bm -= std::log2(0.5 * pw + 0.5 * pc); ++n; a = b; b = w;
        }
    }
    if (!n) { std::puts("[EVAL] no tokens"); return; }
    std::printf("[EVAL] %llu tokens  bits/token: word=%.3f  category=%.3f  mix=%.3f\n", (unsigned long long)n, bw / n, bc / n, bm / n);
}

static void ingestFile(const std::string& path) {
    std::ifstream f(path); if (!f) { std::puts("[ERROR] cannot open file"); return; }
    auto t0 = std::chrono::steady_clock::now(); std::string line; u64 n = 0, bytes = 0;
    while (std::getline(f, line)) { if (!line.empty() && line.back() == '\r') line.pop_back(); if (line.empty()) continue; V.ingest(line); ++n; bytes += line.size() + 1; }
    double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    std::printf("[INGEST] %llu records, %llu bytes in %.3f s (%.2f MB/s)\n", (unsigned long long)n, (unsigned long long)bytes, s, bytes / 1048576.0 / std::max(s, 1e-9));
}

static int selftest() {
    std::mt19937 rng(42); std::vector<std::string> inputs;
    const char* words[] = {"alpha", "beta", "gamma", "the", "a", "zz", "x", "{", "}", ":", ",", "\"k\"", "1", "22"};
    for (int i = 0; i < 3000; ++i) {
        std::string s; int len = 1 + rng() % 25;
        for (int j = 0; j < len; ++j) { s += words[rng() % 14]; if (rng() % 3) s += ' '; }
        if (rng() % 10 == 0) s = std::string(1 + rng() % 30, 'a');
        if (rng() % 10 == 0 && !inputs.empty()) s = inputs[rng() % inputs.size()];
        inputs.push_back(s);
    }
    std::vector<long> ids; for (auto& s : inputs) ids.push_back(V.ingest(s));
    int bad = 0;
    for (size_t i = 0; i < inputs.size(); ++i) if (V.unroll((u32)ids[i]) != inputs[i]) ++bad;
    std::map<std::string, long> firstId; int idBad = 0;
    for (size_t i = 0; i < inputs.size(); ++i) { auto it = firstId.find(inputs[i]); if (it == firstId.end()) firstId[inputs[i]] = ids[i]; else if (it->second != ids[i]) ++idBad; }
    Invariants inv = checkInvariants(V.g);
    V.save("selftest.vtx2"); Vault* keep = new Vault(); std::swap(*keep, V); V.load("selftest.vtx2");
    int bad2 = 0; for (size_t i = 0; i < inputs.size(); ++i) if (V.unroll((u32)ids[i]) != inputs[i]) ++bad2;
    std::printf("[SELFTEST] %zu inputs | round-trip errors: %d | same-text-different-id: %d | after SAVE/LOAD errors: %d\n", inputs.size(), bad, idBad, bad2);
    std::printf("[SELFTEST] grammar invariants: %llu duplicate pairs, %llu under-used rules\n", (unsigned long long)inv.dupDigrams, (unsigned long long)inv.underusedRules);
    return (bad || idBad || bad2) ? 1 : 0;
}

static void help() {
    std::puts(
        "VOLTEX v2.1 — counted grammar memory + inference (no hashes, no weights; training = ingesting)\n"
        "  INGEST <text>        store a record, returns its id (same text -> same id)\n"
        "  INGESTFILE <path>    ingest one record per line\n"
        "  UNROLL <id>          exact reconstruction\n"
        "  AUDIT <id>           show the shared rules a record is built from\n"
        "  FIND <text>          id of an exact record, if stored\n"
        "  METRICS              sizes, invariants, memory\n"
        "  PREDICT <prefix>     next-token distribution (observed vs inferred)\n"
        "  GENERATE [prefix]    sample a continuation (HUNT is an alias)\n"
        "  QUERY <pattern ?>    fill one blank, e.g. QUERY the ? lamp\n"
        "  CLASSES [thresh]     discovered categories (default threshold 0.5)\n"
        "  CONFIG               every setting: value, default, owning layer, experimental or not\n"
        "  RELATIONS            two-argument templates and scored rules\n"
        "  INFER [ALL]          derive facts that were never stated, with proofs\n"
        "  ASK <pattern ?>      stated + inferred answers, e.g. ASK ana is in ?\n"
        "  CONFLICTS            stated facts that contradict what the rules infer\n"
        "  CHAINS [ALL]         derived facts by inference round and tendency-tier steps (ALL: one line per fact)\n"
        "  RETRACT <text>       remove a stored fact and its evidence exactly\n"
        "  UPDATE <text>        replace the subject's earlier value (one-value relations only)\n"
        "  EVAL <path>          held-out bits per token (word / category / mix)\n"
        "  SET RATE|LIFT|SUPPORT|CLASS|PCA|LAW <v>   thresholds\n"
        "  SET COVERAGE|LABELS|CORROBORATE|STALE 0|1  v2.1 behaviours (all 0 == v2.0)\n"
        "  SAVE <path> | LOAD <path> | EXIT");
}

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--selftest") return selftest();
    if (argc > 1 && std::string(argv[1]) == "--version") { std::puts("voltex2 2.2.1"); return 0; }
    settings();   // capture every setting's default before anything can change it
#ifndef _WIN32
    bool tty = isatty(0);
#else
    bool tty = true;
#endif
    if (tty) help();
    std::string line;
    while (true) {
        if (tty) { std::printf("\nvoltex2# "); std::fflush(stdout); }
        if (!std::getline(std::cin, line)) break;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        size_t sp = line.find(' ');
        std::string cmd = line.substr(0, sp), arg = sp == std::string::npos ? "" : line.substr(sp + 1);
        for (auto& c : cmd) c = (char)std::toupper((unsigned char)c);
        if (cmd.empty()) continue;
        struct FlushAfter { ~FlushAfter() { std::fflush(stdout); } } flushAfter_;   // 2.2.1: flush per command so pipes stay interactive
        if (cmd == "HELP") help();
        else if (cmd == "INGEST") { long id = V.ingest(arg); if (id < 0) std::puts("[ERROR] empty"); else std::printf("[INGEST] id %ld\n", id); }
        else if (cmd == "INGESTFILE") ingestFile(arg);
        else if (cmd == "UNROLL") { long id = std::atol(arg.c_str()); if (id < 0 || id >= (long)V.recs.size()) std::puts("[ERROR] no such id"); else std::printf("%s\n", V.unroll((u32)id).c_str()); }
        else if (cmd == "AUDIT") {
            long id = std::atol(arg.c_str()); if (id < 0 || id >= (long)V.recs.size()) { std::puts("[ERROR] no such id"); continue; }
            Sym* s = id == 0 ? V.g.first(V.g.S) : V.recs[id - 1].sep->n;
            std::printf("record %ld (ingested %llu times):\n", id, (unsigned long long)V.recs[id].count);
            for (; s != V.recs[id].sep; s = s->n) audit(s, 1, 3);
        }
        else if (cmd == "FIND") { auto ids = V.toIds(arg); auto it = V.byText.find(ids); if (it == V.byText.end()) std::puts("[FIND] not stored"); else std::printf("[FIND] id %u\n", it->second); }
        else if (cmd == "METRICS") metrics();
        else if (cmd == "PREDICT") predict(arg, 10);
        else if (cmd == "GENERATE" || cmd == "HUNT") { unsigned seed = 1; generate(arg, seed); }
        else if (cmd == "SAMPLE") { int n = std::max(1, std::atoi(arg.c_str())); for (int i = 0; i < n; ++i) std::printf("GEN\t%s\n", generateText("", 1000u + i).c_str()); }
        else if (cmd == "QUERY") fillQuery(arg, 10);
        else if (cmd == "CLASSES") { if (!arg.empty()) { V.classThresh = std::atof(arg.c_str()); V.dirty = true; } showClasses(); }
        else if (cmd == "RELATIONS") showRelations();
        else if (cmd == "INFER") inferCmd(arg);
        else if (cmd == "ASK") ask(arg);
        else if (cmd == "CHAINS") {   // how each derived fact was reached: inference round, tendency-tier steps in its proof
            V.ensureInferred();
            std::map<std::pair<int, int>, u64> by; size_t total = 0;
            for (auto& R : V.rels) for (auto& c : R.chain) { by[c.second]++; ++total; }
            std::printf("[CHAINS] %zu derived facts by inference round and tendency-tier steps in the proof\n", total);
            for (auto& b : by) std::printf("  round %d, tendency steps %d: %llu\n", b.first.first, b.first.second, (unsigned long long)b.second);
            if (arg == "ALL")
                for (auto& R : V.rels) for (auto& c : R.chain)
                    std::printf("CHAIN\t%s\tround=%d\ttendency_steps=%d\n", V.renderFact(R, c.first.first, c.first.second).c_str(), c.second.first, c.second.second);
        }
        else if (cmd == "CONFLICTS") {
            V.ensureInferred();
            std::printf("[CONFLICTS] %zu stated facts contradict what the rules infer\n", V.conflicts.size());
            for (auto& c : V.conflicts) {
                auto& R = V.rels[std::get<0>(c)];
                if (std::get<2>(c) == 0 && std::get<3>(c) == 0) {   // contradiction or undetermined order: no single inferred value
                    std::vector<u32> t = R.tmpl; std::string rel; for (auto x : t) if (x != SLOT) rel += (rel.empty() ? "" : " ") + V.voc.str[x];
                    std::printf("CONFLICT\t%s\t-\t%s | relation: %s\n", V.voc.str[std::get<1>(c)].c_str(), std::get<4>(c).c_str(), rel.c_str());
                    continue;
                }
                bool ov = std::get<4>(c).rfind("OUTVOTED", 0) == 0;   // VOTE: the other value was reported more often, not inferred
                std::printf("CONFLICT\t%s\t%s\tstated: %s | %s: %s | because %s\n", V.voc.str[std::get<1>(c)].c_str(), V.voc.str[std::get<2>(c)].c_str(),
                            V.renderFact(R, std::get<1>(c), std::get<2>(c)).c_str(), ov ? "reported more often" : "inferred", V.renderFact(R, std::get<1>(c), std::get<3>(c)).c_str(), std::get<4>(c).c_str());
            }
        }
        else if (cmd == "EVAL") evalFile(arg);
        else if (cmd == "BUILDS") std::printf("[BUILDS] full %llu, refresh %llu\n", (unsigned long long)V.fullBuilds, (unsigned long long)V.refreshBuilds);
        else if (cmd == "OBSERVE") {   // OBSERVE <source> <record> <time> <revision> <snapshot|partial> | fact ; fact ...
            auto bar = arg.find('|'); std::istringstream hs(arg.substr(0, bar == std::string::npos ? arg.size() : bar));
            Vault::Obs o; std::string scope; hs >> o.src >> o.key >> o.t >> o.rev >> scope;
            if (o.src.empty() || o.key.empty() || (scope != "snapshot" && scope != "partial")) { std::puts("[OBSERVE] usage: OBSERVE <source> <record> <time> <revision> <snapshot|partial> | fact ; fact"); continue; }
            o.snap = scope == "snapshot"; o.seq = V.obsLog.size();
            if (bar != std::string::npos) {
                std::string body = arg.substr(bar + 1); std::stringstream bs(body); std::string fct;
                while (std::getline(bs, fct, ';')) {
                    size_t a = fct.find_first_not_of(" \t"), b = fct.find_last_not_of(" \t");
                    if (a == std::string::npos) { continue; } long id = V.ingest(fct.substr(a, b - a + 1)); if (id >= 0) o.rids.push_back((u32)id);
                }
            }
            V.obsLog.push_back(o); V.dirty = true; V.inferred = false;
            std::printf("[OBSERVE] %s/%s t=%ld rev=%ld %s: %zu fact(s)\n", o.src.c_str(), o.key.c_str(), o.t, o.rev, scope.c_str(), o.rids.size());
        }
        else if (cmd == "SAVE") {
            bool ok = V.save(arg);
            if (ok && !V.obsLog.empty()) {   // the observation log goes in a sidecar file (facts by text)
                std::ofstream o(arg + ".obs");
                for (auto& ob : V.obsLog) {
                    o << ob.src << "\t" << ob.key << "\t" << ob.t << "\t" << ob.rev << "\t" << (ob.snap ? "snapshot" : "partial");
                    for (u32 r : ob.rids) o << "\t" << r;   // v2.2: record ids, not fact text (records keep their order across SAVE/LOAD)
                    o << "\n";
                }
            }
            if (ok) ok = saveConfig(arg);   // settings travel with the knowledge base
            std::puts(ok ? "[SAVE] ok" : "[ERROR] save failed");
        }
        else if (cmd == "LOAD") {
            bool ok = V.load(arg);
            V.obsLog.clear();
            std::ifstream oin(arg + ".obs"); std::string ol;
            while (ok && std::getline(oin, ol)) {
                std::vector<std::string> p; std::stringstream ss(ol); std::string x; while (std::getline(ss, x, '\t')) p.push_back(x);
                if (p.size() < 5) continue;
                Vault::Obs o; o.src = p[0]; o.key = p[1]; o.t = std::stol(p[2]); o.rev = std::stol(p[3]); o.snap = p[4] == "snapshot"; o.seq = V.obsLog.size();
                for (size_t i = 5; i < p.size(); ++i) { u64 r = std::stoull(p[i]); if (r < V.recs.size()) o.rids.push_back((u32)r); }
                V.obsLog.push_back(o);
            }
            V.dirty = true;
            std::puts(ok ? "[LOAD] ok" : "[ERROR] load failed");
            if (ok) loadConfig(arg);
        }
        else if (cmd == "SET") {
            std::istringstream ss(arg); std::string k; double v; ss >> k >> v;
            for (auto& c : k) c = (char)std::toupper((unsigned char)c);
            Setting* st = findSetting(k);
            if (!st) { std::string names; for (auto& x : settings()) { if (!names.empty()) names += " | "; names += x.name; } std::printf("[SET] unknown setting; one of: %s (CONFIG shows them all)\n", names.c_str()); continue; }
            st->set(v);
            V.dirty = true; std::printf("[SET] %s = %g\n", k.c_str(), v);
        }
        else if (cmd == "CONFIG") showConfig();
        else if (cmd == "RETRACT") { auto ids = V.toIds(arg); std::puts(V.retractIds(ids) ? "[RETRACT] removed" : "[RETRACT] not stored"); }
        else if (cmd == "UPDATE") {   // replace the subject's previous value in a one-value relation, then ingest
            V.ensureModel();
            auto ids = V.toIds(arg); auto c = V.content(ids); int removed = 0; bool matched = false;
            for (auto& R : V.rels) {
                if (R.tmpl.size() != c.size()) continue;
                std::vector<size_t> sl; bool ok = true;
                for (size_t i = 0; i < c.size(); ++i) { if (R.tmpl[i] == SLOT) sl.push_back(i); else if (R.tmpl[i] != c[i]) ok = false; }
                if (!ok || sl.size() != 2) continue;
                std::map<u32, int> per; for (auto& f : R.stated) per[f.first]++;
                size_t single = 0; for (auto& x : per) if (x.second == 1) ++single;
                if (!per.empty() && double(single) / double(per.size()) < 0.9) { std::puts("[UPDATE] relation has several values per subject; use RETRACT for the old fact"); break; }
                matched = true;
                std::vector<std::vector<u32>> victims;
                for (auto& kv : V.byText) {
                    auto c2 = V.content(kv.first);
                    if (c2.size() != c.size()) continue;
                    bool same = true; for (size_t i = 0; i < c.size(); ++i) if (i != sl[1] && c2[i] != c[i]) same = false;
                    if (same && c2[sl[1]] != c[sl[1]]) victims.push_back(kv.first);
                }
                for (auto& v : victims) removed += V.retractIds(v);
                V.touched.insert(c[sl[0]]);
                for (auto& R2 : V.rels) for (auto& f : R2.stated) if (f.second == c[sl[0]]) V.touched.insert(f.first);   // one hop: things that point at it
                break;
            }
            long id = V.ingest(arg);
            std::printf("[UPDATE] %s; replaced %d earlier value(s); id %ld\n", matched ? "relation matched" : "no relation template yet, plain ingest", removed, id);
        }
        else if (cmd == "ECHO") std::puts(arg.c_str());   // 2.2.1: lets a client mark the end of each reply
        else if (cmd == "EXIT") break;
        else std::puts("Unknown command. Type HELP.");
    }
    return 0;
}
