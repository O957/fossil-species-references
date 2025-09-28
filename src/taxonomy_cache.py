"""
Persistent cache functions for taxonomy search results using parquet format.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import polars as pl

from config_loader import NOT_AVAILABLE


# cache file location
CACHE_FILE = Path(__file__).parent.parent / "data" / "results.parquet"


def load_cache() -> pl.DataFrame:
    """
    Load existing cache or create empty DataFrame.

    Returns
    -------
    pl.DataFrame
        Cache dataframe with taxonomy results.
    """
    if CACHE_FILE.exists():
        try:
            return pl.read_parquet(str(CACHE_FILE))
        except:
            pass

    # create empty dataframe with schema
    return pl.DataFrame(schema={
        "search_term": pl.Utf8,
        "taxonomic_authority": pl.Utf8,
        "year": pl.Int64,
        "author": pl.Utf8,
        "reference": pl.Utf8,
        "doi": pl.Utf8,
        "paper_link": pl.Utf8,
        "source": pl.Utf8,
        "year_mismatch": pl.Boolean,
        "timestamp": pl.Datetime,
    })


def lookup_in_cache(search_term: str) -> Optional[Dict[str, Any]]:
    """
    Look up a search term in the cache.

    Parameters
    ----------
    search_term : str
        The taxonomic name to search for.

    Returns
    -------
    Optional[Dict[str, Any]]
        Cached result if found, None otherwise.
    """
    cache_df = load_cache()

    if cache_df.is_empty():
        return None

    # case-insensitive search
    result = cache_df.filter(
        pl.col("search_term").str.to_lowercase() == search_term.lower()
    )

    if not result.is_empty():
        # return most recent result
        result = result.sort("timestamp", descending=True).limit(1)
        return result.to_dicts()[0]

    return None


def save_to_cache(result: Dict[str, Any]):
    """
    Save a new result to the cache.

    Parameters
    ----------
    result : Dict[str, Any]
        Result dictionary to save.
    """
    # load current cache
    cache_df = load_cache()

    # prepare result for saving
    result = result.copy()
    result.pop("from_cache", None)  # remove from_cache field if present

    # add timestamp
    result["timestamp"] = datetime.now()

    # ensure all required fields exist
    for field in ["search_term", "taxonomic_authority", "year", "author",
                  "reference", "doi", "paper_link", "source", "year_mismatch"]:
        if field not in result:
            if field == "year":
                result[field] = None
            elif field == "year_mismatch":
                result[field] = False
            else:
                result[field] = NOT_AVAILABLE

    # convert year to int if possible
    if result["year"] and result["year"] != NOT_AVAILABLE:
        try:
            result["year"] = int(result["year"])
        except:
            result["year"] = None
    else:
        result["year"] = None

    # append to dataframe
    new_row = pl.DataFrame([result])
    cache_df = pl.concat([cache_df, new_row], how="vertical")

    # save to disk
    cache_df.write_parquet(str(CACHE_FILE))


def clear_cache():
    """Clear the entire cache by creating an empty file."""
    empty_df = pl.DataFrame(schema={
        "search_term": pl.Utf8,
        "taxonomic_authority": pl.Utf8,
        "year": pl.Int64,
        "author": pl.Utf8,
        "reference": pl.Utf8,
        "doi": pl.Utf8,
        "paper_link": pl.Utf8,
        "source": pl.Utf8,
        "timestamp": pl.Datetime,
    })
    empty_df.write_parquet(str(CACHE_FILE))


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns
    -------
    Dict[str, Any]
        Statistics about the cache.
    """
    cache_df = load_cache()

    if cache_df.is_empty():
        return {
            "count": 0,
            "recent": [],
            "sources": {}
        }

    # count by source
    source_counts = {}
    if "source" in cache_df.columns:
        counts_df = cache_df.group_by("source").agg(pl.count().alias("count"))
        for row in counts_df.to_dicts():
            source_counts[row["source"]] = row["count"]

    # recent searches
    recent = cache_df.sort("timestamp", descending=True).limit(10)
    recent_list = recent.select("search_term", "source", "timestamp").to_dicts()

    return {
        "count": len(cache_df),
        "recent": recent_list,
        "sources": source_counts
    }