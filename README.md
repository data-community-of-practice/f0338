# f0338
# Organisation Classifier

A Python script that classifies research organisations into **Research**, **Health**, **Government**, or **Industry** using a three-tier approach that prioritises deterministic sources over LLM inference.

## Four categories

| Category | What it covers |
|---|---|
| **Research** | Universities, research institutes, academic centres, learned societies, research foundations, medical research institutes |
| **Health** | Hospitals, health services, clinical networks, medical centres, mental health services, rehabilitation centres, teaching hospitals |
| **Government** | Government departments, agencies, regulatory bodies, national labs (e.g., CSIRO, NIH), statutory bodies, councils |
| **Industry** | Private companies, corporations, pharmaceutical companies, technology companies, consulting firms |

## Classification strategy

The script processes organisations through three tiers, stopping at the first successful classification:

### Tier 1 — ROR metadata (instant, fully deterministic)

Uses the `Type` field from the ROR API:

| ROR Type | Classification |
|---|---|
| `education` | Research |
| `healthcare` | Health |
| `government` | Government |
| `company` | Industry |
| `nonprofit` | Research |
| `facility` | Government |
| `archive` | Government |

This alone typically classifies 50–70% of organisations.

### Tier 2 — Wikidata (deterministic, API-based)

For organisations not classified by Tier 1, the script searches Wikidata by name, retrieves the `instance of` (P31) property, and matches against curated lists of Wikidata entity types for each category. Priority order: Research > Health > Government > Industry.

### Tier 3 — Claude LLM (cached for reproducibility)

For the remaining unclassified organisations, the script queries the Anthropic Claude API with `temperature=0` for a deterministic response. Results are cached so re-runs produce identical output.

## Requirements

- Python 3.7+
- Libraries: `openpyxl`, `requests`
- An Anthropic API key (optional — Tier 3 is skipped without one)

```bash
pip install openpyxl requests
```

## Setup

Update `config.ini` with your Anthropic API key:

```ini
[crossref]
email = yourname@example.com
delay = 1
save_every = 50
max_retries = 3

[anthropic]
api_key = sk-ant-your-key-here
```

The LLM tier is optional. Leave `api_key` empty to run Tiers 1 and 2 only.

## Usage

### From a terminal

```bash
python classify_orgs.py unique_orgs.xlsx
```

### From Spyder

```python
!python "E:\your\folder\classify_orgs.py" "E:\your\folder\unique_orgs.xlsx"
```

## Output

The script produces `<input_name>_classified.xlsx` with these columns:

| Column | Description |
|---|---|
| `Organisation_Name` | Canonical name |
| `Classification` | **Research**, **Health**, **Government**, **Industry**, or **Unclassified** |
| `Classification_Source` | Which tier succeeded: `ROR`, `Wikidata`, `LLM`, or `None` |
| `Justification` | Why this classification was chosen |
| `ROR_ID`, `Country`, `City`, `ROR_Type` | Organisation metadata |
| `Raw_Variants` | Raw affiliation strings that resolved to this org |
| `Author_Count`, `Authors`, `DOI_Count`, `DOIs` | Linked researchers and publications |

Classifications are colour-coded: blue for Research, purple for Health, green for Government, red for Industry, yellow for Unclassified.

## Reproducibility

| Tier | Deterministic? | How |
|---|---|---|
| ROR | Yes | Same type always maps to the same classification |
| Wikidata | Yes | Same entity always has the same P31 claims |
| LLM | Practically yes | `temperature=0` + cached results |

All results are cached. Deleting a cache file forces re-classification for that tier only.

## Cache files

| File | Purpose |
|---|---|
| `<input>_wikidata_cache.json` | Wikidata entity lookups and P31 results |
| `<input>_llm_cache.json` | Claude API classifications |

## Full pipeline

This is step 5 in the pipeline:

```
1. python crossref_author_fetch.py <input>.xlsx
     → adds Crossref_Authors column

2. python extract_unique_authors.py <step1_output>.xlsx
     → one row per unique author with DOIs

3. python fetch_affiliations.py <step2_output>.xlsx
     → adds Affiliations column (Crossref + OpenAlex)

4. python extract_unique_orgs.py <step3_output>.xlsx
     → one row per unique institution with ROR ID

5. python classify_orgs.py <step4_output>.xlsx
     → adds Classification column (Research/Health/Government/Industry)
```

## Troubleshooting

| Problem | Solution |
|---|---|
| LLM tier skipped | Add your Anthropic API key to `config.ini` under `[anthropic]` `api_key`. |
| Many "Unclassified" orgs | Add an API key to enable Tier 3, which handles the remaining orgs. |
| Wikidata matches wrong entity | Wikidata search by name can return the wrong entity for ambiguous names. Check the `Justification` column. |
| API rate limits | Increase `delay` in config.ini. |
| Old cache causing wrong results | Delete the relevant `_wikidata_cache.json` or `_llm_cache.json` and re-run. |

## License

This script is provided as-is for research and data management purposes.
