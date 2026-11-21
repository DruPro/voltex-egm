"""Temporary layer: real-world data interpretation -> facts (studies/stress). Separate from the code layer.

Real tables found on any Debian/Ubuntu machine, each a different shape:
  packages()  dpkg status: depends on, is in section, has priority, is for architecture, provides
              (dependency graph with hub values; maintainer names are never read)
  unicode()   Python unicodedata: has category, has bidi class, is in script, has uppercase, has lowercase,
              decomposes to, has property mirrored, has combining class (large attribute tables with inverse pairs)
  timezones() tz database: is in country, is in area, country has name word (hierarchy, many-to-one)
  services()  /etc/services: uses port, uses protocol, is alias of (small, flat)

Each returns (facts, stats). Names are single tokens (letters, digits, _).
"""
import os, re, unicodedata
from codebase import tok


def packages(path="/var/lib/dpkg/status"):
    facts, n = set(), 0
    for block in open(path, encoding="utf-8", errors="replace").read().split("\n\n"):
        f = {}
        for line in block.splitlines():
            m = re.match(r"^([A-Za-z-]+):\s*(.*)$", line)
            if m: f[m.group(1)] = m.group(2)
        if "Package" not in f or "installed" not in f.get("Status", ""): continue
        n += 1; p = tok("pkg_" + f["Package"])
        for key, rel in (("Depends", "depends on"), ("Pre-Depends", "depends on"), ("Recommends", "recommends"),
                         ("Provides", "provides")):
            for alt in f.get(key, "").split(","):
                d = alt.split("|")[0].strip().split(" ")[0].split(":")[0]
                if d and tok("pkg_" + d) != p: facts.add(f"{p} {rel} {tok('pkg_' + d)}")
        if f.get("Section"): facts.add(f"{p} is in section {tok('sec_' + f['Section'])}")
        if f.get("Priority"): facts.add(f"{p} has priority {tok('prio_' + f['Priority'])}")
        if f.get("Architecture"): facts.add(f"{p} is for architecture {tok('arch_' + f['Architecture'])}")
        if f.get("Source"): facts.add(f"{p} is built from {tok('src_' + f['Source'].split(' ')[0])}")
    return sorted(facts), {"packages": n}


def unicode(lo=0x20, hi=0x3000):
    facts, n = set(), 0
    for cp in range(lo, hi):
        ch = chr(cp); name = unicodedata.name(ch, None)
        if not name: continue
        n += 1; c = f"u{cp:04X}"
        facts.add(f"{c} has category {tok('cat_' + unicodedata.category(ch))}")
        facts.add(f"{c} has bidi class {tok('bidi_' + unicodedata.bidirectional(ch))}")
        facts.add(f"{c} is in script {tok('script_' + name.split(' ')[0])}")
        if unicodedata.mirrored(ch): facts.add(f"{c} has property mirrored")
        cc = unicodedata.combining(ch)
        if cc: facts.add(f"{c} has combining class {tok('ccc_' + str(cc))}")
        up, low = ch.upper(), ch.lower()
        if len(up) == 1 and up != ch: facts.add(f"{c} has uppercase u{ord(up):04X}")
        if len(low) == 1 and low != ch: facts.add(f"{c} has lowercase u{ord(low):04X}")
        dec = unicodedata.decomposition(ch)
        if dec and not dec.startswith("<"):
            base = dec.split(" ")[0]; facts.add(f"{c} decomposes to u{int(base, 16):04X}")
    return sorted(facts), {"characters": n}


def timezones(root="/usr/share/zoneinfo"):
    facts, names = set(), {}
    for line in open(os.path.join(root, "iso3166.tab"), encoding="utf-8"):
        if line.startswith("#") or not line.strip(): continue
        cc, nm = line.rstrip("\n").split("\t")[:2]; names[cc] = nm
    zones = 0
    for line in open(os.path.join(root, "zone.tab"), encoding="utf-8"):
        if line.startswith("#") or not line.strip(): continue
        cc, _, z = line.rstrip("\n").split("\t")[:3]; zones += 1
        t = tok("tz_" + z); facts.add(f"{t} is in country {tok('cc_' + cc)}"); facts.add(f"{t} is in area {tok('area_' + z.split('/')[0])}")
    for cc, nm in names.items():
        for w in nm.split(" "):
            w = tok(w)
            if w and len(w) > 2: facts.add(f"{tok('cc_' + cc)} has name word {tok('w_' + w.lower())}")
    return sorted(facts), {"zones": zones, "countries": len(names)}


def services(path="/etc/services"):
    facts = set()
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.split("#")[0].split()
        if len(line) < 2 or "/" not in line[1]: continue
        port, proto = line[1].split("/"); s = tok("svc_" + line[0])
        facts.add(f"{s} uses port {tok('port_' + port)}"); facts.add(f"{s} uses protocol {tok('proto_' + proto)}")
        for a in line[2:]: facts.add(f"{tok('svc_' + a)} is alias of {s}")
    return sorted(facts), {}
