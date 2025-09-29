#!/usr/bin/env python3
"""
Script to populate the taxonomy cache from PBDB data.

This script reads the PBDB parquet file and adds entries to the cache,
skipping entries without references. It also attempts to find CrossRef
DOIs and paper links for the references.
"""

import sys
import time
from pathlib import Path

# Add src to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import polars as pl

from config_loader import API_DELAY, NOT_AVAILABLE
from database_queries import extract_author, extract_year, query_crossref
from taxonomy_cache import load_cache, save_to_cache


def process_pbdb_entry(row: dict) -> dict | None:
    """
    Process a single PBDB entry into cache format.

    Parameters
    ----------
    row : dict
        PBDB row data.

    Returns
    -------
    dict | None
        Cache entry or None if no reference available or year mismatch.
    """
    # Skip if no reference
    ref = row.get("ref")
    if not ref or ref == NOT_AVAILABLE or ref == "null" or not ref.strip():
        return None

    # Extract taxonomic authority and other fields
    search_term = row.get("nam", "").strip()
    taxonomic_authority = row.get("att", NOT_AVAILABLE)

    if not search_term:
        return None

    # Extract year and author from authority
    year = (
        extract_year(taxonomic_authority)
        if taxonomic_authority != NOT_AVAILABLE
        else None
    )
    author = (
        extract_author(taxonomic_authority)
        if taxonomic_authority != NOT_AVAILABLE
        else NOT_AVAILABLE
    )

    # STRICT YEAR VALIDATION: only accept references where year matches authority year
    if not year:
        # No year in taxonomic authority - cannot validate, skip entry
        return None

    ref_year = extract_year(ref)
    if ref_year != year:
        # Year mismatch - skip this entry entirely
        return None

    # Get DOI from PBDB if available
    doi = row.get("doi", NOT_AVAILABLE)
    if doi in [None, "null", ""]:
        doi = NOT_AVAILABLE

    # Create base result
    result = {
        "search_term": search_term,
        "taxonomic_authority": taxonomic_authority,
        "year": year,
        "author": author,
        "reference": ref,
        "doi": doi,
        "paper_link": NOT_AVAILABLE,
        "source": "PBDB",
        "year_mismatch": False,
    }

    return result


def add_crossref_info(result: dict) -> dict:
    """
    Add CrossRef DOI and paper link to result if not already present.

    Parameters
    ----------
    result : dict
        Cache entry.

    Returns
    -------
    dict
        Updated cache entry with CrossRef info.
    """
    # Only query CrossRef if we don't already have a DOI
    if result["doi"] == NOT_AVAILABLE and result["reference"] != NOT_AVAILABLE:
        try:
            crossref_result = query_crossref(
                result["reference"], result["author"], result["year"]
            )

            if crossref_result:
                if crossref_result["doi"] != NOT_AVAILABLE:
                    result["doi"] = crossref_result["doi"]
                if crossref_result["paper_link"] != NOT_AVAILABLE:
                    result["paper_link"] = crossref_result["paper_link"]

            # Small delay to be respectful to CrossRef API
            time.sleep(API_DELAY)

        except Exception as e:
            print(f"CrossRef error for {result['search_term']}: {e}")

    return result


def main():
    """Main function to populate cache from PBDB data."""
    print("🦴 Populating taxonomy cache from PBDB data...")

    # Load PBDB data
    pbdb_file = (
        Path(__file__).parent.parent
        / "data"
        / "pbdb_essential_taxonomy_with_refs.parquet"
    )
    if not pbdb_file.exists():
        print(f"❌ PBDB file not found: {pbdb_file}")
        return

    print(f"📖 Loading PBDB data from {pbdb_file}")
    df = pl.read_parquet(str(pbdb_file))
    print(f"📊 Total PBDB entries: {len(df)}")

    # Filter entries with references
    has_refs = df.filter(
        pl.col("ref").is_not_null()
        & (pl.col("ref") != NOT_AVAILABLE)
        & (pl.col("ref") != "null")
        & (pl.col("ref").str.len_chars() > 0)
    )
    print(f"📚 Entries with references: {len(has_refs)}")

    # Load existing cache to avoid duplicates
    existing_cache = load_cache()
    if not existing_cache.is_empty():
        existing_terms = set(existing_cache["search_term"].str.to_lowercase())
        print(f"🗃️  Existing cache entries: {len(existing_cache)}")
    else:
        existing_terms = set()
        print("🗃️  Starting with empty cache")

    # Process entries
    added_count = 0
    skipped_count = 0
    error_count = 0
    no_ref_count = 0
    year_mismatch_count = 0
    no_auth_year_count = 0

    print(f"\n🔄 Processing {len(has_refs)} entries...")
    print("📊 Progress will be shown every 50 entries...")
    print(
        "⚠️  Only entries with matching reference year will be added to cache"
    )

    for i, row in enumerate(has_refs.to_dicts()):
        try:
            # Skip if already in cache
            search_term = row.get("nam", "").strip().lower()
            if search_term in existing_terms:
                skipped_count += 1

                # Show progress every 50 entries
                if (i + 1) % 50 == 0:
                    progress = (i + 1) / len(has_refs) * 100
                    print(
                        f"📈 {progress:.1f}% ({i + 1}/{len(has_refs)}) | ✅ Added: {added_count} | ⏭️ Skipped: {skipped_count} | ❌ Errors: {error_count} | 📝 No ref: {no_ref_count} | ⚠️ Year mismatch: {year_mismatch_count} | 📅 No auth year: {no_auth_year_count}"
                    )
                continue

            # Process entry - check specific reason for rejection
            ref = row.get("ref")
            if (
                not ref
                or ref == NOT_AVAILABLE
                or ref == "null"
                or not ref.strip()
            ):
                no_ref_count += 1
                continue

            # Check for year validation before processing
            taxonomic_authority = row.get("att", NOT_AVAILABLE)
            if taxonomic_authority == NOT_AVAILABLE:
                no_auth_year_count += 1
                continue

            auth_year = extract_year(taxonomic_authority)
            if not auth_year:
                no_auth_year_count += 1
                continue

            ref_year = extract_year(ref)
            if ref_year != auth_year:
                year_mismatch_count += 1
                continue

            result = process_pbdb_entry(row)
            if result is None:
                no_ref_count += (
                    1  # Should not happen anymore, but just in case
                )
                continue

            # Show what we're processing
            if added_count < 10 or (added_count + 1) % 25 == 0:
                print(
                    f"   🔍 Processing: {result['search_term']} ({result['year'] or 'no year'})"
                )

            # Add CrossRef info (with API delay)
            result = add_crossref_info(result)

            # Save to cache
            save_to_cache(result)
            added_count += 1
            existing_terms.add(search_term)

            # Progress update every 50 entries
            if (i + 1) % 50 == 0:
                progress = (i + 1) / len(has_refs) * 100
                print(
                    f"📈 {progress:.1f}% ({i + 1}/{len(has_refs)}) | ✅ Added: {added_count} | ⏭️ Skipped: {skipped_count} | ❌ Errors: {error_count} | 📝 No ref: {no_ref_count} | ⚠️ Year mismatch: {year_mismatch_count} | 📅 No auth year: {no_auth_year_count}"
                )

        except Exception as e:
            error_count += 1
            print(f"❌ Error processing {row.get('nam', 'unknown')}: {e}")

        # Optional: limit for testing (remove in production)
        # if added_count >= 50:
        #     print("🛑 Stopping early for testing")
        #     break

    print("\n✅ Cache population complete!")
    print(f"   📝 Added: {added_count} entries")
    print(f"   ⏭️  Skipped (already cached): {skipped_count} entries")
    print(f"   ❌ Errors: {error_count} entries")
    print(f"   ⚠️  Year mismatches (not added): {year_mismatch_count} entries")
    print(f"   📅 No authority year (not added): {no_auth_year_count} entries")

    # Final cache stats
    final_cache = load_cache()
    print(f"   🗃️  Final cache size: {len(final_cache)} entries")


if __name__ == "__main__":
    main()
