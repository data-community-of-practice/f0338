# f0338
# Extract Researcher Nodes and Publication Relationships

A Python script that reads the organisation-enriched researcher file from [f0337](https://github.com/data-community-of-practice/f0337), produces a slim researcher identity table and a researcher-to-publication relationship table, and attempts to fill in missing ORCID identifiers via a name search against the ORCID public API.

No API key required.

## Pipeline context

```
f0334  →  Crossref_AuthorMetadata.json
f0335  →  Normalised_Authors.json
f0335a →  Resolved_Authors.json
f0336  →  Authors_With_Affiliations.json
f0336a →  Authors_With_Affiliations.json   (further enriched)
f0337  →  Organisations.json + Researcher_Organisation.json + Authors_Enriched.json
f0338  →  Researchers.json + Researcher_Publication.json
```

By this stage the full researcher objects (with affiliations, name variants, publication lists) have been split into specialised tables by f0337. f0338 produces the final researcher identity nodes and the researcher-publication edge table — the two remaining pieces needed to fully represent the grant-researcher-publication graph.

## How it works

1. **Load** — reads `Authors_Enriched.json` (output of f0337).
2. **ORCID lookup** — for each researcher missing an ORCID, searches the ORCID public API by name (primary name first, then all name variants). Only accepts a result when **exactly one** record is returned — this conservative threshold prevents false positives for common names.
3. **Build researcher nodes** — extracts the identity fields from each author into a slim record.
4. **Build publication relationships** — flattens each author's publication list into one relationship record per unique researcher-DOI pair.

## Outputs

| File | Description |
|------|-------------|
| `Researchers.json` | One node per researcher with identity fields only. |
| `Researcher_Publication.json` | Relationship records pairing researcher UUIDs to publication DOIs. |
| `orcid_name_lookup_cache.json` | Cached ORCID name-search results. Enables resumable runs. |

### Researcher node

```json
{
  "id": "3f2a1b4c-...",
  "given": "Jane",
  "family": "Doe",
  "full_name": "Jane Doe",
  "orcid": "0000-0001-2345-6789"
}
```

| Field | Description |
|-------|-------------|
| `id` | UUID carried forward from the pipeline. Consistent across all output files. |
| `given` | Best available given name. |
| `family` | Family name. |
| `full_name` | Combined given and family name. |
| `orcid` | ORCID identifier, or `null` if not found. |

### Researcher-publication relationship record

```json
{
  "researcher_id": "3f2a1b4c-...",
  "publication_doi": "10.1111/example.12345"
}
```

One record per unique researcher-DOI pair. A researcher who appears on five papers generates five records. Duplicate pairs (same researcher, same DOI from different sources) are deduplicated automatically.

## ORCID name lookup

For researchers without an ORCID from earlier pipeline steps, the script queries:

```
https://pub.orcid.org/v3.0/search/?q=family-name:"Doe" AND given-names:"Jane"
```

It tries the primary name first, then each entry in `name_variants`. A match is accepted only when the API returns **exactly one result** — if two or more researchers share the same name, no ORCID is assigned to avoid misattribution. Results (including `null` outcomes) are cached in `orcid_name_lookup_cache.json` so re-runs skip already-searched names.

## Requirements

- Python 3.7+
- Library: `requests`

```bash
pip install requests
```

No API key or registration required.

## Usage

```bash
python f0338.py
```

By default, reads `Authors_Enriched.json` from the current directory (then the script directory) and writes outputs alongside it.

Specify paths explicitly:

```bash
python f0338.py path/to/Authors_Enriched.json --output-dir ./output/
```

### All options

| Option | Description |
|--------|-------------|
| `input_json` | Input file (default: `Authors_Enriched.json`). |
| `--output-dir`, `-o` | Directory for output files (default: same as input). |
| `--skip-orcid-lookup` | Skip ORCID name searches entirely. Use when offline or when ORCID coverage is already sufficient. |

### From Spyder or Jupyter

```python
!python "E:\your\folder\f0338.py" "E:\your\folder\Authors_Enriched.json"
```

## Console output

```
Input:        /path/to/Authors_Enriched.json
Output:       /path/to/
ORCID lookup: enabled

Authors in input: 2075
Missing ORCID:    1184

ORCID cache:      0 entries

Looking up ORCIDs for 1184 researchers...
  [1/1184] Jane Doe -> 0000-0001-2345-6789
  [2/1184] J. Smith -> not found
  [3/1184] Wei Zhang -> not found
  ...

ORCID lookup: found 203/1184

=======================================================
EXTRACTION SUMMARY
=======================================================
Researchers:               2075
  With ORCID:              1094
  Without ORCID:           981
Researcher-Pub links:      8432
Unique DOIs linked:        412
=======================================================

Saved:
  Researchers:       /path/to/Researchers.json
  Researcher-Pub:    /path/to/Researcher_Publication.json
```

## Resuming an interrupted run

ORCID name-search results are cached in `orcid_name_lookup_cache.json`. Re-running skips all previously searched names — both hits and confirmed misses. Only researchers whose names have never been searched incur API calls.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ERROR: pip install requests` | Run `pip install requests` and retry. |
| Low ORCID discovery rate | Expected — ORCID name search only accepts single-result matches to avoid false positives. Researchers with common names (e.g. "Wei Zhang") will not be matched even if they have an ORCID. |
| ORCID lookup is slow | Each name variant incurs a 0.5 s delay. Use `--skip-orcid-lookup` to skip and produce outputs immediately if ORCID coverage from earlier steps is sufficient. |
| ORCID rate limit errors (429) | The script backs off automatically. If errors persist, re-run — the cache preserves all completed lookups. |
| Want to retry previously missed names | Delete `orcid_name_lookup_cache.json` and re-run to search all names from scratch. |

## Limitations

- **Conservative ORCID matching**: only researchers with a unique name in the ORCID registry receive a match. This avoids false positives but leaves common names unresolved.
- **Name variant splitting**: variant names are split on the last space to separate given and family name. Multi-word family names without a comma separator may be split incorrectly.
- **No affiliation or full publication metadata in output**: `Researchers.json` contains identity fields only. Full publication details (titles, years) and affiliation data live in the upstream files (`Authors_Enriched.json`, `Organisations.json`).

## License

This script is provided as-is for research and data management purposes.
