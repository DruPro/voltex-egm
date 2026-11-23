# Round 2 confirmation real data

Built by `realdata2.py build` from sources on this machine. No engine ran on any of these sets before the
pre-registration was hashed. The sources' hashes, fact counts per split and stated-fact hashes are in
`realdata/manifest.json`.

| set | source | relations | facts | per split |
|---|---|---|---|---|
| `c_headers` | `/usr/include`, first 400,000 lines in sorted walk order (stress `codebase.c_headers`) | includes, is declared in, is a, has field of type, returns, aliases | 18,791 | ~14,900 stated, ~3,900 hidden |
| `timezones` | `/usr/share/zoneinfo/zone.tab`, `iso3166.tab` (stress `world.timezones`) | is in country, is in area, has name word | 1,167 | ~940 / ~230 |
| `services` | `/etc/services` (stress `world.services`) | uses port, uses protocol, is alias of | 659 | ~520 / ~140 |
| `py_requires` | installed Python distributions (`importlib.metadata`) | requires (unconditional `Requires-Dist`), has extra, provides module | 604 | ~470 / ~130 |

**Truth:** the extracted facts, which are complete for their definition. A fact not extracted is false. So, as
with Round 1's dpkg, a derived transitive `includes` or `requires` counts as wrong. That is strict: such a fact
may be true in the transitive sense, which the definition excludes.

**Splits:** seeds 2000 to 2004. Each fact is hidden with probability 0.2 (`random.Random(seed)`). The hidden facts
are the recall truth.

**Independence:**

- **From Round 2 development:** dpkg, Unicode and the two Python codebases were Round 1 confirmation sets and are
  Round 2 development data. These four sets were not used in either round's development, design or scoring.
- **The stress bench** (Round 1's K-H0) ran the legacy profile over its own builds of the C-header, time-zone and
  services layers and compared the output to the legacy binary byte for byte. Nothing was scored against truth,
  and no Round 2 profile has run on them.
- **`py_requires`** is a different relation set from the same machine's installed packages. Round 1's `py_dist`
  extracted code facts (classes, calls) from `dist-packages`, not package metadata.
