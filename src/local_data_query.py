"""
Local data query module for PBDB data from parquet file.
This module replaces PBDB API calls with local data queries.
"""

import re
from pathlib import Path

import polars as pl

from config_loader import NOT_AVAILABLE

# cache the dataframe to avoid reloading
_cached_df = None


def load_pbdb_data() -> pl.DataFrame:
    """
    Load the PBDB data from the parquet file.

    Returns
    -------
    pl.DataFrame
        The loaded PBDB data.
    """
    global _cached_df
    if _cached_df is None:
        data_path = Path(__file__).parent.parent / "data" / "pbdb_essential_taxonomy_with_refs.parquet"
        _cached_df = pl.read_parquet(str(data_path))
    return _cached_df


def extract_author_from_ref(ref_text: str) -> str:
    """
    Extract author from reference text.

    Parameters
    ----------
    ref_text : str
        Full reference text.

    Returns
    -------
    str
        Extracted author or NOT_AVAILABLE.
    """
    if not ref_text or ref_text == "null":
        return NOT_AVAILABLE

    # typical format: "Author. Year. Title..."
    # extract first part before year
    parts = ref_text.split(".")
    if len(parts) > 0:
        # the first part is usually the author
        return parts[0].strip()
    return NOT_AVAILABLE


def extract_year_from_ref(ref_text: str) -> str:
    """
    Extract year from reference text.

    Parameters
    ----------
    ref_text : str
        Full reference text.

    Returns
    -------
    str
        Extracted year or NOT_AVAILABLE.
    """
    if not ref_text or ref_text == "null":
        return NOT_AVAILABLE

    # look for 4-digit year pattern
    year_match = re.search(r"\b(1[789]\d{2}|20[012]\d)\b", ref_text)
    if year_match:
        return year_match.group(1)
    return NOT_AVAILABLE


def query_pbdb_local(organism_name: str) -> dict | None:
    """
    Query local PBDB dataset (parquet file) for a given organism.

    Note: This searches the locally stored PBDB data file,
    not the online PBDB API.

    Parameters
    ----------
    organism_name : str
        The scientific name of the organism to look up.

    Returns
    -------
    dict | None
        Dictionary containing publication info, error info,
        or None if not found.
    """
    try:
        df = load_pbdb_data()

        # search for exact match first
        result = df.filter(pl.col("nam") == organism_name)

        # if no exact match, try case-insensitive
        if len(result) == 0:
            result = df.filter(
                pl.col("nam").str.to_lowercase() == organism_name.lower()
            )

        # if still no match, try contains
        if len(result) == 0:
            result = df.filter(
                pl.col("nam").str.contains(organism_name, literal=False)
            )

        if len(result) == 0:
            return None

        # take the first result
        record = result[0].to_dict()

        # convert to expected format
        nam = record.get("nam", [organism_name])[0] if "nam" in record else organism_name
        att = record.get("att", [NOT_AVAILABLE])[0] if "att" in record else NOT_AVAILABLE
        ref = record.get("ref", [NOT_AVAILABLE])[0] if "ref" in record else NOT_AVAILABLE

        # handle null values from parquet
        if att == "null" or att is None:
            att = NOT_AVAILABLE
        if ref == "null" or ref is None:
            ref = NOT_AVAILABLE

        # extract author and year from reference
        ref_author = extract_author_from_ref(ref)
        ref_year = extract_year_from_ref(ref)

        return {
            "nam": nam,
            "att": att,
            "ref": ref,
            "aut": ref_author,  # author from reference
            "pby": ref_year,    # publication year from reference
        }

    except Exception as e:
        return {"error": f"Local data query error: {e}", "organism": organism_name}


def query_multiple_species_local(
    species_list: list[str],
) -> tuple[list[dict], list[str], list[dict]]:
    """
    Query local PBDB data for multiple species.

    Parameters
    ----------
    species_list : list[str]
        List of species names to query.

    Returns
    -------
    tuple[list[dict], list[str], list[dict]]
        (successful_results, not_found_species, error_results)
    """
    results = []
    not_found = []
    errors = []

    for species in species_list:
        record = query_pbdb_local(species.strip())

        if record is None:
            not_found.append(species)
        elif "error" in record:
            errors.append({"organism": species, "error": record["error"]})
        else:
            results.append(record)

    return results, not_found, errors