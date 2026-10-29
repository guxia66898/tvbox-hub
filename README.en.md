# tvbox-hub · TVBox / YingShiCang source hub

[![CI](https://github.com/guxia66898/tvbox-hub/actions/workflows/hub.yml/badge.svg)](https://github.com/guxia66898/tvbox-hub/actions/workflows/hub.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)

A self-hosted pipeline that turns scattered public TVBox / YingShiCang (影视仓) config URLs into a
maintainable subscription, and keeps it honest with daily availability checks.

```
seed list + aggregator pages
        ↓  harvest
full-ecosystem config parser  (lenient JSON · image stego · CatVod 2423 AES · Base64)
        ↓  L1 probe
line availability  (recursive multi-warehouse expansion, TTFB / latency grading)
        ↓  L2 probe
site-level sampling  (CMS API reachability for type 0/1 sites)
        ↓  merge
single-warehouse config  (global spider voting + per-site jar allocation)
        ↓
merged.json · curated.json · tvbox.json · report.json · index.html (dashboard)
```

> **Scope**: availability checking and format normalisation only. The project does not host,
> mirror, or redistribute any media content. It fetches publicly published configuration files
> and reports whether their endpoints respond.

中文说明见 [README.md](README.md)。

---

## Why it exists

Public TVBox config URLs rot fast: a list that works today is half-dead next month, and no client
tells you which entries died. Existing tools each cover a slice — one harvests, one merges, one
tests site APIs — but nothing runs the whole chain and keeps history.

tvbox-hub closes that loop, and adds two self-sustaining mechanisms:

1. **Auto-discovery** — every run scans index pages (awesome lists / aggregator READMEs), Codeberg's
   public API, optionally GitHub search, then enumerates candidate config files via jsDelivr. Every
   candidate must be fetched and successfully parsed before it enters `seeds/auto.json`.
2. **Auto-promotion** — child lines expanded out of multi-warehouse configs are tracked run over run;
   once a line stays available for N consecutive runs it is promoted into `seeds/promote.json` and
   probed as a first-class seed from then on (no longer dependent on its parent warehouse).

Both live in machine-managed state files and never touch the hand-curated `seeds/lines.json`.

## Quick start

```bash
cd tvbox-hub
pip install pycryptodome                      # only needed for CatVod 2423 AES

# self-check first — fully offline, ~2 seconds
python tests/test_parser.py        # lenient JSON / 2423 AES / stego / Base64
python tests/test_merge.py         # spider voting / per-site jar / dedupe / dirty-data cleaning
python tests/test_hub_offline.py   # artifact writing / dashboard / diffing
python tests/test_discover.py      # four discovery channels / verification gate / pruning
python tests/test_promote.py       # promotion lifecycle
python tests/test_jarcheck.py      # jar reachability

# full pipeline: harvest + discover + L1 + L2
python run.py --config config.example.json
```

Outputs land in `dist/`; history snapshots in `history/`. Open `dist/index.html` in a browser for
the dashboard.

### GitHub Actions (recommended)

`.github/workflows/hub.yml` runs daily at 21:30 UTC, then commits `dist/` and `history/` back to the
repository. Point GitHub Pages at `dist/` and you get a daily-updated subscription URL plus a live
health dashboard, with no server of your own.

### Docker

```bash
docker build -t tvbox-hub .
docker run --rm -v $PWD/config.json:/app/config.json \
           -v $PWD/dist:/app/dist -v $PWD/history:/app/history tvbox-hub
```

## Artifacts

| File | Shape | Consumed by |
|---|---|---|
| `dist/merged.json` | `{"urls":[{"name","url"},…]}` multi-warehouse | YingShiCang / multi-warehouse-aware TVBox |
| `dist/curated.json` | same, hand-picked seeds only | when you want a small stable set |
| `dist/tvbox.json` | merged single-warehouse config | FongMi / plain TVBox |
| `dist/report.json` | full probe tree + diff vs previous run | tooling, archiving |
| `dist/index.html` | static dashboard (no external assets) | humans |
| `dist/jar_health.json` | reachability per spider jar | diagnostics |

Ranking: available single-warehouse lines are ordered by `L2 pass rate → latency`;
score = 40 base + L2×30 (neutral 12 when unsampled) + speed ≤20 + site count ≤10.

## The parser library

`tvbox_config_parser` is usable standalone — it handles every config dialect this ecosystem uses:

```python
from tvbox_config_parser import parse_payload

payload = parse_payload(resp_bytes)
payload.kind         # 'single' | 'multi_storehouse' | 'multi_urls' | 'unknown'
payload.format       # 'plain_json' | 'json_relaxed' | 'image_stego' | 'aes_hex' | 'base64_json'
payload.sub_entries  # [(name, url), …] for multi-warehouse configs
payload.raw_obj      # the parsed dict
```

- **lenient JSON** — a character-level state machine strips `//` and `/* */` comments and trailing
  commas without corrupting `"http://"` inside strings.
- **image steganography** — configs appended after an image's EOF marker as `**` + Base64.
- **CatVod `2423`** — `$#key#$…` AES-128-CBC hex payloads, supporting both 13-byte timestamp IVs
  (zero-padded to 16) and full 16-byte IVs.
- **pure Base64** configs.
- **aggregator page extraction** — keyword-filtered URL harvesting from index pages.

Zero third-party dependencies; `pycryptodome` is imported lazily only when a `2423` payload appears.

## Verification model

| Layer | Checks | Coverage |
|---|---|---|
| **L1 line** | config URL reachable, parseable, kind recognised; recursive multi-warehouse expansion (depth 2–3, ≤40–100 children, node cap); median TTFB / total / size with grading (fast <500 ms, mid <2 s, slow <5 s) | all lines |
| **L2 site** | CMS API reachability for `type 0/1` sites, searchable-first sampling, pass rate per warehouse | type 0/1 only |
| **jar** | reachability probe for every referenced spider jar; sites pointing at dead jars are flagged `jar_dead` | type 3 dependency |

Type-3 spider sites need their jar loaded by the client, so they cannot be verified server-side —
"unsampled" in the dashboard does not mean "broken".

## Auto-discovery and promotion

```
seeds/lines.json     hand-curated, never modified by the tool
seeds/discovered.json  bulk import from a discovery session (optional)
seeds/auto.json      machine-managed: discovered + verified config URLs, with health counters
seeds/promote.json   machine-managed: child lines that earned promotion, with ok/fail streaks
```

Discovery channels, in order of reliability: index-page mining → Codeberg public search →
GitHub repository search (only with `GITHUB_TOKEN`; the anonymous 60/hour quota is far too small) →
jsDelivr file-tree enumeration. Gate: a candidate must fetch **and** parse into a single- or
multi-warehouse config with actual content. In practice ~96 index-page candidates yielded 1–3
genuinely new sources per run — everything else was already known or dead.

Promotion needs accumulation: default `promote_after = 3` consecutive available runs, pruned after
5 consecutive failures. In a real three-run sequence the third run promoted 84 child lines.

```bash
python run.py --no-discover       # skip discovery
python run.py --no-promote        # skip promotion
python run.py --promote-after 2   # promote sooner (aggressive)
python run.py --no-jar-check      # skip jar probing (saves 30–60 s)
```

## Safety

- **SSRF guard** — DNS is resolved and private / loopback / link-local / CGNAT / reserved ranges
  (including IPv4-mapped IPv6) are rejected by default. `--allow-private` is for local debugging only.
- **Hard response cap** (4 MB default) against oversized streams and decompression bombs.
- **Supply-chain signal** — configs whose `spider` is plain `http://` are flagged
  `has_cleartext_spider` in reports.
- **No content stored** — history snapshots keep URLs and metrics only.

## Test run (2026-10-29, real network)

| Stage | Result |
|---|---|
| Seeds | 125 hand-curated + 2 auto-discovered + 84 promoted |
| Top-level lines / nodes | 236 / 546 |
| Available | 233 (185 single + 46 multi) |
| L2 sampled | 77 warehouses |
| Merged config | **6936 sites across 274 jars**, with 763 sites flagged `jar_dead` (54 of 274 jars unreachable, 19.7 %) |
| Audit | 0 structural defects (keys, API schemes, jar schemes, artifact consistency) |

## Known limits

- L2 covers `type 0/1` only; type-3 spider sites require client-side jar loading.
- Promotion needs accumulated runs — nothing promotes on the first day.
- `jar_dead` is a flag, not a deletion: jars can be temporarily down.
- Upstream sources disappear without notice. That is exactly why this runs daily.

## Relationship to other projects

| Project | What it does | What tvbox-hub took from it |
|---|---|---|
| 影视仓接口助手 v1.0 (APK, reverse-engineered) | on-device harvest + verify + export | seed table, recursion/measurement semantics, multi-warehouse export shape |
| [yz8023/ysc-helper-android](https://github.com/yz8023/ysc-helper-android) | native rewrite of the same app | exact `2423` AES and steganography implementation, SSRF blocklist |
| [zhuzhuyule/juhe-subhub](https://github.com/zhuzhuyule/juhe-subhub) | subscription detection and assembly | three-artifact layout, daily-run model |
| [fish2018/tvbox](https://github.com/fish2018/tvbox) | interface privatisation / dedupe | normalisation and proxy-prefix stripping |
| [lyrhub/tvbox-checker-app](https://github.com/lyrhub/tvbox-checker-app) | site-level connectivity and speed tests | L2 sampling design |
| [tengxiaobao/tvbox-source-aggregator](https://gitee.com/tengxiaobao/tvbox-source-aggregator) | multi-source merge service | **`hub/merge.py` blueprint**: relative-path resolution, global spider voting, per-site `jar` allocation, `key\|api` dedupe with suffixing, host-based rule merging |

## License

MIT — see [LICENSE](LICENSE).
