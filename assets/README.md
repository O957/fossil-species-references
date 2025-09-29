# Cache Population Scripts

This directory contains scripts for populating the taxonomy cache with data from the PBDB (Paleobiology Database) file.

## Scripts

### `populate_cache_from_pbdb.py`

Main script that processes the entire PBDB dataset and adds entries to the cache.

**Features:**
- Skips entries without references
- Avoids duplicates by checking existing cache
- Attempts to find CrossRef DOIs and paper links
- Provides progress updates every 100 entries
- Respects API rate limits with delays

**Usage:**
```bash
cd assets
python3 populate_cache_from_pbdb.py
```

**Safe to run multiple times** - it will skip entries already in the cache.

### `test_cache_population.py`

Test script that processes only 5 sample entries for validation.

**Usage:**
```bash
cd assets
python3 test_cache_population.py
```

## What the scripts do

1. **Load PBDB data** from `../data/pbdb_essential_taxonomy_with_refs.parquet`
2. **Filter entries** that have valid references (skips empty or null references)
3. **Check existing cache** to avoid duplicate processing
4. **Process each entry**:
   - Extract taxonomic authority, year, and author
   - Use the full reference from PBDB
   - Set source as "PBDB"
5. **Query CrossRef** to find DOIs and paper links (with API delays)
6. **Save to cache** using the same system as the Streamlit app

## Expected output

The script will show progress like:
```
🦴 Populating taxonomy cache from PBDB data...
📖 Loading PBDB data from ../data/pbdb_essential_taxonomy_with_refs.parquet
📊 Total PBDB entries: 454716
📚 Entries with references: 454713
🗃️  Existing cache entries: 21
🔄 Processing 454713 entries...
📈 Progress: 0.0% (100/454713) - Added: 95, Skipped: 5
...
```

## Notes

- The script is respectful to APIs with built-in delays
- Entries without references are automatically skipped
- CrossRef queries may not always find matches (especially for older papers)
- The cache will be populated with complete PBDB references, which are typically more detailed than GBIF references
