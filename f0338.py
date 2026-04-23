#!/usr/bin/env python3
"""
Extract Researcher Nodes + Publication Relationships
======================================================
Reads the enriched authors JSON from the pipeline and produces
two clean JSON files:

  1. Researchers.json -- researcher nodes with:
     - id (UUID primary key)
     - given, family, full_name
     - orcid (looked up from ORCID API if missing)

  2. Researcher_Publication.json -- relationship records:
     - researcher_id (UUID)
     - publication_doi (string)

For researchers without an ORCID, the script searches the ORCID
public API by name (trying name variants). Only accepts a match
when exactly one result is returned to avoid false positives.

No API key required (ORCID public API).

Usage:
  python f0338.py [Authors_Enriched.json] [--output-dir ./output]
  python f0338.py --skip-orcid-lookup
"""

import sys
import json
import time
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: pip install requests")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = "Authors_Enriched.json"
ORCID_API = "https://pub.orcid.org/v3.0/search/"


# ============================================================
# ORCID LOOKUP
# ============================================================

def search_orcid_by_name(given, family, session, max_retries=2):
    """
    Search ORCID public API by name.
    Returns ORCID ID only if exactly one result is found.
    """
    if not family:
        return None

    # Build query
    if given:
        query = f'family-name:"{family}" AND given-names:"{given}"'
    else:
        query = f'family-name:"{family}"'

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(
                ORCID_API,
                params={"q": query, "rows": 5},
                headers={"Accept": "application/json"},
                timeout=15,
            )

            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue

            if resp.status_code != 200:
                return None

            data = resp.json()
            num_found = data.get("num-found", 0)
            results = data.get("result", [])

            # Only accept exact single match
            if num_found == 1 and results:
                return results[0].get("orcid-identifier", {}).get("path")

            return None

        except requests.exceptions.RequestException:
            if attempt < max_retries:
                time.sleep(1)
            else:
                return None

    return None


def try_orcid_lookup(researcher, session, cache):
    """
    Try to find an ORCID for a researcher by searching name variants.
    Returns ORCID ID or None.
    """
    # Try the primary name first
    given = researcher.get("given", "")
    family = researcher.get("family", "")

    cache_key = f"{given}|{family}".lower().strip()
    if cache_key in cache:
        return cache[cache_key]

    orcid = search_orcid_by_name(given, family, session)
    if orcid:
        cache[cache_key] = orcid
        return orcid

    # Try name variants
    for variant in researcher.get("name_variants", []):
        parts = variant.strip().rsplit(" ", 1)
        if len(parts) == 2:
            v_given, v_family = parts
        else:
            v_given = ""
            v_family = parts[0]

        v_key = f"{v_given}|{v_family}".lower().strip()
        if v_key == cache_key or v_key in cache:
            continue

        time.sleep(0.5)
        orcid = search_orcid_by_name(v_given, v_family, session)
        cache[v_key] = orcid

        if orcid:
            cache[cache_key] = orcid
            return orcid

    cache[cache_key] = None
    return None


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract researcher nodes and publication relationships"
    )
    parser.add_argument("input_json", nargs="?", default=None,
                        help=f"Input JSON (default: {DEFAULT_INPUT})")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="Output directory (default: same as input)")
    parser.add_argument("--skip-orcid-lookup", action="store_true",
                        help="Skip ORCID API lookups for researchers without ORCIDs")
    args = parser.parse_args()

    # Resolve paths
    if args.input_json:
        input_path = Path(args.input_json).resolve()
    else:
        input_path = Path.cwd() / DEFAULT_INPUT
        if not input_path.exists():
            input_path = SCRIPT_DIR / DEFAULT_INPUT

    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    researchers_path = output_dir / "Researchers.json"
    rels_path = output_dir / "Researcher_Publication.json"
    cache_path = output_dir / "orcid_name_lookup_cache.json"

    print(f"Input:        {input_path}")
    print(f"Output:       {output_dir}")
    print(f"ORCID lookup: {'skipped' if args.skip_orcid_lookup else 'enabled'}")
    print()

    # Load
    with open(input_path, "r", encoding="utf-8") as f:
        authors = json.load(f)

    print(f"Authors in input: {len(authors)}")

    # Count missing ORCIDs
    missing_orcid = [a for a in authors if not a.get("orcid")]
    print(f"Missing ORCID:    {len(missing_orcid)}")

    # ORCID lookup for those missing
    if not args.skip_orcid_lookup and missing_orcid:
        # Load cache
        orcid_cache = {}
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                orcid_cache = json.load(f)
            print(f"ORCID cache:      {len(orcid_cache)} entries")

        session = requests.Session()
        found = 0

        def safe(s):
            return s.encode("ascii", errors="replace").decode("ascii")

        print(f"\nLooking up ORCIDs for {len(missing_orcid)} researchers...")
        for i, a in enumerate(missing_orcid, 1):
            name = a.get("full_name", "")
            print(f"  [{i}/{len(missing_orcid)}] {safe(name)}", end=" ", flush=True)

            orcid = try_orcid_lookup(a, session, orcid_cache)

            if orcid:
                a["orcid"] = orcid
                found += 1
                print(f"-> {orcid}")
            else:
                print("-> not found")

            time.sleep(0.5)

        # Save cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(orcid_cache, f, ensure_ascii=False, indent=2)

        print(f"\nORCID lookup: found {found}/{len(missing_orcid)}")

    # Build researcher nodes
    researchers = []
    relationships = []
    seen_rels = set()

    for a in authors:
        researcher = {
            "id": a["id"],
            "given": a.get("given", ""),
            "family": a.get("family", ""),
            "full_name": a.get("full_name", ""),
            "orcid": a.get("orcid"),
        }
        researchers.append(researcher)

        # Build publication relationships
        for p in a.get("publications", []):
            if isinstance(p, dict):
                doi = p.get("doi", "")
            else:
                doi = str(p)

            if doi:
                rel_key = (a["id"], doi)
                if rel_key not in seen_rels:
                    seen_rels.add(rel_key)
                    relationships.append({
                        "researcher_id": a["id"],
                        "publication_doi": doi,
                    })

    # Save
    with open(researchers_path, "w", encoding="utf-8") as f:
        json.dump(researchers, f, ensure_ascii=False, indent=2)

    with open(rels_path, "w", encoding="utf-8") as f:
        json.dump(relationships, f, ensure_ascii=False, indent=2)

    # Summary
    with_orcid = sum(1 for r in researchers if r.get("orcid"))
    without_orcid = len(researchers) - with_orcid

    print(f"\n{'='*55}")
    print(f"EXTRACTION SUMMARY")
    print(f"{'='*55}")
    print(f"Researchers:               {len(researchers)}")
    print(f"  With ORCID:              {with_orcid}")
    print(f"  Without ORCID:           {without_orcid}")
    print(f"Researcher-Pub links:      {len(relationships)}")
    print(f"Unique DOIs linked:        {len(set(r['publication_doi'] for r in relationships))}")
    print(f"{'='*55}")
    print(f"\nSaved:")
    print(f"  Researchers:       {researchers_path}")
    print(f"  Researcher-Pub:    {rels_path}")


if __name__ == "__main__":
    main()