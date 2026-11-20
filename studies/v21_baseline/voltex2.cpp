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
};
struct RuleH {
    char type;          // 'I' inverse/symmetric, 'T' transitive, 'C' composition
    int r1, r2, r3;     // premise relations, conclusion relation
    u64 n = 0, k = 0;   // chains seen, chains whose conclusion is also stated
    double rate = 0, base = 0, lift = 0; u64 pn = 0; double pca = 0; bool accepted = false;
    double cov = -1, rel = 0; bool law = false;   // completeness used, reliability, label
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
    void buildClasses(size_t maxWords = 12000) {
        size_t V = voc.str.size();
        cls.assign(V, 0); for (u32 i = 0; i < V; ++i) cls[i] = i;
        std::vector<u32> wordsv;
        for (u32 w = 2; w < V; ++w) if (w < wc.uni.size() && wc.uni[w] && !voc.space[w]) wordsv.push_back(w);
        std::sort(wordsv.begin(), wordsv.end(), [&](u32 a, u32 b) { return wc.uni[a] > wc.uni[b]; });
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
        for (u32 r = 0; r < recs.size(); ++r) if (recs[r].count) recContent.push_back(content(recIds(r)));
        auto keyFor = [&](const std::vector<u32>& c, size_t i, size_t j) { auto k = c; k[i] = SLOT; k[j] = SLOT; return k; };
        auto openPos = [&](const std::vector<u32>& c) { std::vector<size_t> p; for (size_t i = 0; i < c.size(); ++i) if (open(c[i])) p.push_back(i); return p; };
        for (auto& c : recContent) {
            auto p = openPos(c); if (p.size() < 2 || p.size() > 8) continue;
            for (size_t x = 0; x < p.size(); ++x) for (size_t y = x + 1; y < p.size(); ++y) support[keyFor(c, p[x], p[y])]++;
        }
        std::map<std::vector<u32>, int> relIdx;
        for (auto& c : recContent) {
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
        }
        std::sort(rels.begin(), rels.end(), [](auto& a, auto& b) { return a.stated.size() > b.stated.size(); });
        if (rels.size() > 40) rels.resize(40);
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
        if (F_COV || F_LABELS) rescoreRules(subj);
        std::sort(ruleList.begin(), ruleList.end(), [](auto& a, auto& b) { return a.accepted != b.accepted ? a.accepted : a.lift > b.lift; });
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
            double cR = covRel[h.r3] > 0 ? covRel[h.r3] : covGlobal; h.cov = cR;
            double bar = (F_COV && cR > 0) ? std::min(RATE_MIN, RATE_REL * cR) : RATE_MIN;   // relax for sparse data, never tighten
            bool classic = h.lift >= LIFT_MIN && h.rate >= bar;
            double ex = double(h.pn) * h.base, sd = std::sqrt(std::max(1e-9, ex * (1 - h.base)));
            bool pcaOk = h.pn >= 5 && h.pca >= PCA_MIN && (double(h.k) - ex) / sd >= 3.0;
            h.accepted = h.k >= K_MIN && (classic || pcaOk);
            h.rel = functional[h.r3] ? h.pca : (cR > 0 ? std::min(1.0, h.rate / cR) : h.rate);
            h.law = h.rel >= LAW_MIN;
        }
        (void)subj;
    }
    std::string ruleText(const RuleH& h) const {
        auto nm = [&](int r) { return "[" + words(rels[r].tmpl) + "]"; };
        if (h.type == 'I') return nm(h.r1) + "(a,b) => " + nm(h.r3) + "(b,a)";
        return nm(h.r1) + "(a,b) & " + nm(h.r2) + "(b,c) => " + nm(h.r3) + "(a,c)";
    }

    // deduction to a fixpoint: every derived fact carries its proof
    void infer(int maxDepth = 4) {
        for (auto& R : rels) { R.derived.clear(); R.lawDerived.clear(); }
        conflicts.clear();
        std::vector<bool> functional(rels.size());
        std::vector<std::map<u32, std::set<u32>>> objs(rels.size());
        for (size_t i = 0; i < rels.size(); ++i) {
            for (auto& f : rels[i].stated) objs[i][f.first].insert(f.second);
            size_t single = 0; for (auto& o : objs[i]) if (o.second.size() == 1) ++single;
            functional[i] = !objs[i].empty() && double(single) / double(objs[i].size()) >= 0.95;
        }
        std::set<std::pair<int, u32>> conflicted;
        auto has = [&](int r, u32 a, u32 b) { return rels[r].stated.count({a, b}) || rels[r].derived.count({a, b}); };
        auto conf = [&](int r, u32 a, u32 b) { if (rels[r].stated.count({a, b})) return 1.0; return rels[r].derived.at({a, b}).first; };
        for (int depth = 0; depth < maxDepth; ++depth) {
            std::vector<std::tuple<int, u32, u32, double, std::string>> add;
            // functional relations: every derivation path is a vote, including paths that agree with what is stated
            std::map<std::pair<int, u32>, std::map<u32, std::pair<int, std::string>>> votes;
            std::map<std::pair<int, u32>, std::map<u32, int>> lawVotes;   // law-tier paths per value
            std::set<std::tuple<int, u32, u32>> lawAdd;
            bool curLaw = false; int curRule = -1;
            std::map<std::pair<int, u32>, std::map<u32, std::set<int>>> ruleVotes;   // distinct rules per value
            auto isLaw = [&](int r, u32 a, u32 b) { return rels[r].stated.count({a, b}) || rels[r].lawDerived.count({a, b}); };
            auto propose = [&](int r3, u32 a, u32 c, double score, std::string why) {
                if (functional[r3]) { auto& v = votes[{r3, a}][c]; if (v.first++ == 0) v.second = why; if (curLaw) lawVotes[{r3, a}][c]++; ruleVotes[{r3, a}][c].insert(curRule); return; }
                if (!has(r3, a, c)) { add.emplace_back(r3, a, c, score, why); if (curLaw) lawAdd.insert({r3, a, c}); }
            };
            for (auto& h : ruleList) {
                if (!h.accepted) continue;
                curRule = int(&h - &ruleList[0]);
                auto all = [&](int r) { std::vector<std::pair<u32, u32>> v(rels[r].stated.begin(), rels[r].stated.end()); for (auto& d : rels[r].derived) v.push_back(d.first); return v; };
                if (h.type == 'I') {
                    for (auto& f : all(h.r1)) if (f.first != f.second && ((curLaw = F_LABELS && h.law && isLaw(h.r1, f.first, f.second)) || true))
                        propose(h.r3, f.second, f.first, h.rate * conf(h.r1, f.first, f.second),
                                renderFact(rels[h.r1], f.first, f.second) + "  [rule: " + ruleText(h) + "]");
                } else {
                    std::map<u32, std::vector<u32>> out2; for (auto& f : all(h.r2)) out2[f.first].push_back(f.second);
                    for (auto& f : all(h.r1)) {
                        auto it = out2.find(f.second); if (it == out2.end()) continue;
                        for (u32 c : it->second) if (c != f.first && ((curLaw = F_LABELS && h.law && isLaw(h.r1, f.first, f.second) && isLaw(h.r2, f.second, c)) || true))
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
                if (it == D.end() || it->second.first < std::get<3>(t)) D[key] = {std::get<3>(t), std::get<4>(t)};
                if (lawAdd.count({std::get<0>(t), std::get<1>(t), std::get<2>(t)})) rels[std::get<0>(t)].lawDerived.insert(key);
            }
        }
        inferred = true;
    }
    static double nowms() { return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
    void ensureModel() {
        if (!dirty) return;
        double t0 = nowms(); buildClasses(); double t1 = nowms(); buildRelations(); double t2 = nowms(); mineRules(); double t3 = nowms();
        if (F_PROFILE) std::printf("[PROFILE] classes %.1f ms | relations %.1f ms | rule mining %.1f ms\n", t1 - t0, t2 - t1, t3 - t2);
        dirty = false; inferred = false;
    }
    void ensureInferred() { ensureModel(); if (!inferred) { double t0 = nowms(); infer(); if (F_PROFILE) std::printf("[PROFILE] infer %.1f ms\n", nowms() - t0); } }

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
    std::printf("[RELATIONS] %zu two-argument templates\n", V.rels.size());
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
        std::printf("  %s %-60s n=%llu k=%llu rate=%.2f lift=%.1f | where answer known: %llu, agree=%.2f%s\n", h.accepted ? "ACCEPT" : "reject", V.ruleText(h).c_str(),
                    (unsigned long long)h.n, (unsigned long long)h.k, h.rate, h.lift, (unsigned long long)h.pn, h.pca, extra);
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
        for (auto& f : R.stated) if (fits(f.first, f.second)) { std::printf("  %-32s stated\n", V.renderFact(R, f.first, f.second).c_str()); ++answers; }
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
        "  RELATIONS            two-argument templates and scored rules\n"
        "  INFER [ALL]          derive facts that were never stated, with proofs\n"
        "  ASK <pattern ?>      stated + inferred answers, e.g. ASK ana is in ?\n"
        "  CONFLICTS            stated facts that contradict what the rules infer\n"
        "  RETRACT <text>       remove a stored fact and its evidence exactly\n"
        "  UPDATE <text>        replace the subject's earlier value (one-value relations only)\n"
        "  EVAL <path>          held-out bits per token (word / category / mix)\n"
        "  SET RATE|LIFT|SUPPORT|CLASS|PCA|LAW <v>   thresholds\n"
        "  SET COVERAGE|LABELS|CORROBORATE|STALE 0|1  v2.1 behaviours (all 0 == v2.0)\n"
        "  SAVE <path> | LOAD <path> | EXIT");
}

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--selftest") return selftest();
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
        else if (cmd == "CONFLICTS") {
            V.ensureInferred();
            std::printf("[CONFLICTS] %zu stated facts contradict what the rules infer\n", V.conflicts.size());
            for (auto& c : V.conflicts) {
                auto& R = V.rels[std::get<0>(c)];
                std::printf("CONFLICT\t%s\t%s\tstated: %s | inferred: %s | because %s\n", V.voc.str[std::get<1>(c)].c_str(), V.voc.str[std::get<2>(c)].c_str(),
                            V.renderFact(R, std::get<1>(c), std::get<2>(c)).c_str(), V.renderFact(R, std::get<1>(c), std::get<3>(c)).c_str(), std::get<4>(c).c_str());
            }
        }
        else if (cmd == "EVAL") evalFile(arg);
        else if (cmd == "SAVE") std::puts(V.save(arg) ? "[SAVE] ok" : "[ERROR] save failed");
        else if (cmd == "LOAD") std::puts(V.load(arg) ? "[LOAD] ok" : "[ERROR] load failed");
        else if (cmd == "SET") {
            std::istringstream ss(arg); std::string k; double v; ss >> k >> v;
            for (auto& c : k) c = (char)std::toupper((unsigned char)c);
            if (k == "RATE") V.RATE_MIN = v; else if (k == "LIFT") V.LIFT_MIN = v; else if (k == "SUPPORT") V.K_MIN = (u64)v;
            else if (k == "CLASS") V.classThresh = v; else if (k == "PCA") V.PCA_MIN = v;
            else if (k == "COVERAGE") V.F_COV = (int)v; else if (k == "LABELS") V.F_LABELS = (int)v; else if (k == "CORROBORATE") V.F_CORROB = (int)v;
            else if (k == "STALE") V.F_STALE = (int)v; else if (k == "LAW") V.LAW_MIN = v; else if (k == "PROFILE") V.F_PROFILE = (int)v;
            else { std::puts("[SET] RATE | LIFT | SUPPORT | CLASS | PCA | LAW <value>, or COVERAGE | LABELS | CORROBORATE | STALE | PROFILE 0/1"); continue; }
            V.dirty = true; std::printf("[SET] %s = %g\n", k.c_str(), v);
        }
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
        else if (cmd == "EXIT") break;
        else std::puts("Unknown command. Type HELP.");
    }
    return 0;
}
