#!/usr/bin/env python3
"""
Test script to validate cache population with a small sample.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import polars as pl
from populate_cache_from_pbdb import add_crossref_info, process_pbdb_entry

from taxonomy_cache import load_cache


def main():
    """Test the cache population with a small sample."""
    print("🧪 Testing cache population...")

    # Load PBDB data and take a small sample
    pbdb_file = (
        Path(__file__).parent.parent
        / "data"
        / "pbdb_essential_taxonomy_with_refs.parquet"
    )
    df = pl.read_parquet(str(pbdb_file))

    # Get a small sample with references
    sample = df.filter(
        pl.col("ref").is_not_null()
        & (pl.col("ref") != "Not available")
        & (pl.col("ref") != "null")
        & (pl.col("ref").str.len_chars() > 0)
    ).limit(5)

    print(f"Testing with {len(sample)} entries:")

    for i, row in enumerate(sample.to_dicts()):
        print(f"\n--- Entry {i + 1}: {row['nam']} ---")
        print(f"Authority: {row.get('att', 'N/A')}")
        print(f"Reference: {row.get('ref', 'N/A')[:100]}...")

        # Process entry
        result = process_pbdb_entry(row)
        if result:
            print("✅ Processed successfully")
            print(f"Year: {result['year']}")
            print(f"Author: {result['author']}")

            # Test CrossRef (but don't save)
            print("🔍 Testing CrossRef...")
            result_with_crossref = add_crossref_info(result.copy())
            if result_with_crossref["doi"] != "Not available":
                print(f"Found DOI: {result_with_crossref['doi']}")
            if result_with_crossref["paper_link"] != "Not available":
                print(f"Found link: {result_with_crossref['paper_link']}")
        else:
            print("❌ No reference found")

    print(f"\n🗃️ Current cache size: {len(load_cache())} entries")


if __name__ == "__main__":
    main()
