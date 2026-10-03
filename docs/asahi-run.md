# Asahi-class live run — 2026-09-23

Entity: modern JMSDF Asahi-class destroyer, lead ship DD-119 Asahi and sister ship
DD-120 Shiranui. The separate 1955 Asahi destroyer escort is not the target.
Model: `xiaomi/mimo-v2.6-flash`; one extraction call, with a synthetic test key provided
at hidden prompt. The key is not included in either result file.

## Files

- Original collected source, model response and first-pass validation:
  `output/asahi/c008cf4014cb4ff091fd5552bfec076f.json`
- Revalidated from the saved original model claims after fixing Japanese full-width numeric
  evidence parsing (no second model call):
  `output/asahi/c008cf4014cb4ff091fd5552bfec076f.reviewed.json`
- Revalidated with the current Asahi profile's equipment filter (still no second model call):
  `output/asahi/c008cf4014cb4ff091fd5552bfec076f.filtered.json`
- Reusable revalidation command: `python scripts/reprocess_saved.py <run.json>`

The run reached the official JMSDF equipment page. It returned a Japanese page with an explicit
reuse note requiring attribution as “Source: Japan Maritime Self-Defense Force website”; preserve
that attribution if republishing derived data. [Official JMSDF Asahi class page](https://www.mod.go.jp/msdf/equipment/ships/dd/asahi/).

The Wikipedia API source was refused by the current local robots policy before retrieving the
article. The run therefore completed as `partial`; no alternate Wikipedia mirror was used.

## Extracted from the official page

| Field | Result | Evidence from source |
|---|---:|---|
| Name | `護衛艦「あさひ」型` | Class heading |
| Type | `護衛艦` | Same heading |
| Length | 150.5 m | `長さ １５０．５ｍ` |
| Beam | 18.3 m | `幅 １８．３ｍ` |
| Standard displacement | 5,100 t | `基準排水量 : ５,１００ｔ` |
| Speed | 30 kn | `速力 : ３０ｋｔ` |
| Armament | Four weapon/launcher entries after filtering | `主要兵装` row; full text retained in `raw_value` |

The page also states hull depth as 10.9 m, but the original schema had `draft` and no `depth`.
The model correctly left draft missing instead of calling depth draft. The Asahi profile now has a
separate `depth` field. This run is not silently backfilled with a value the model was never asked
to extract. Crew and full-load displacement are not given on the official page and remain missing.

## Algorithm findings

1. **Fixed from this run:** the original validator rejected 150.5 and 18.3 because full-width
   Japanese digits, decimal point and unit were not normalized in evidence scanning. It accepted
   5,100 t and 30 kn. The original quotes remain unchanged; only a normalized comparison copy is
   used now. Reprocessing accepts all seven claims and records no validation issues.
2. **Schema improvement:** a source can say “depth” where the profile asks “draft”. Those are
   different measurements. Added a separate `depth` field; do not map them onto one field.
3. **Source access:** robots currently disallows the configured English Wikipedia API URL, so that
   branch stops and is reported. Respect the denial; an operator can use a different source only
   if that source grants access. The official JMSDF page sufficed for this one-pass sample.
4. **Attribution:** unlike an unqualified internal scrape, the official page explicitly asks for
   JMSDF attribution when quoting/reposting. The source URL and original Japanese text are retained.
5. **Still needs review:** one model call on one page shows the extraction path works; it does not
   establish extraction quality on long articles, variant-specific values, or conflicting sources.
   Normalizing armament into weapon systems, count, caliber and variant will need a structured
   nested-field schema.

## Filter review after the first report

The original `armament` value contained 11 Japanese list items because the source groups
weapons and electronics together under `主要兵装`. Four entries are guns/launchers:
`高性能２０ミリ機関砲×２`, `ＶＬＳ装置`, `６２口径５インチ砲×１`, `水上発射管×２`.
The other seven entries are radar, sonar, torpedo-defense, electronic-warfare and information
systems. The configurable string-list filter now removes those seven from the normalized
`armament` value. It keeps the complete original string in `raw_value` and lists every removed
entry in `excluded_segments`. This is a field-specific rule for the Japanese Asahi profile,
not a global assumption that every source uses the same terminology.

The reviewed file's numerical values remain unchanged. `origin_country`, `draft`, `depth`,
`displacement_full_load` and `crew` are missing in the filtered file. `depth` was added to
the profile after the model call, so the recorded response never attempted to extract it.
Field-specific filtering is a useful first correction; a later structured equipment schema
should separate weapons, sensors, defenses and C4I rather than storing a single long string.

## Expanded review after source audit

The first extraction used a narrow 12-field profile. The saved official JMSDF class page
contains additional facts that were missed by that schema. These are source-backed
observations, not a second model run:

| Category | Source-backed value | Scope |
|---|---|---|
| Propulsion | 2 gas turbines, 2 propulsion electric motors, 2 shafts | Class page |
| Rated power | 62,500 PS | Class page |
| 20 mm gun mounts | 2 | Class page |
| 5-inch/62-caliber gun mounts | 1 | Class page |
| VLS | Present; cell count unstated | Class page |
| Surface launch tube assemblies | 2; tubes per assembly unstated | Class page |
| Radar | Multifunction radar, navigation radar; model names unstated | Class page |
| Sonar | Surface-ship sonar system, towed passive sonar; model names unstated | Class page |
| Other systems | Torpedo-defense, EW, information-processing systems | Class page |
| Hull depth | 10.9 m, distinct from draft | Class page |
| Crew | Approximately 220 | Official PDF, DD-119 Asahi ship entry |
| Draft | 5.4 m | Official PDF, DD-119 Asahi ship entry |
| Range/endurance | No value verified from these official sources | Missing |

The [official JMSDF ship PDF](https://www.mod.go.jp/msdf/asd/IMAGE/CONTENTS/PDF/TOPICS/kantei.pdf)
(page 6 of the PDF) describes DD-119 Asahi, while the
[class page](https://www.mod.go.jp/msdf/equipment/ships/dd/asahi/) describes the class.
The PDF lists 5,050 t, 151 m and 62,600 horsepower, while the class page lists
5,100 t, 150.5 m and 62,500 PS. Keep these as source-specific statements rather than
silently reconciling them. The PDF crew value is approximate and ship-specific.
No verified official range or endurance was found; a third-party estimate should not
be promoted to an observed value.

The Asahi configuration now requests propulsion, power, weapon counts, separate
sensor/defense systems, range and endurance. A new model run has not yet been made
because COMMANDCODE_API_KEY is not set in the current session. The previous
filtered JSON remains a record of the earlier run.