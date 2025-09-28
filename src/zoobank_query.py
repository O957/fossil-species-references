"""
ZooBank query module for taxonomic information.
This module queries ZooBank for species information and falls back to PBDB dataset.
"""

import requests
from pathlib import Path

import polars as pl

from config_loader import NOT_AVAILABLE

# cache the PBDB dataframe for fallback
_cached_pbdb_df = None


def load_pbdb_data_fallback() -> pl.DataFrame:
    """
    Load the PBDB data from the parquet file as fallback.

    Returns
    -------
    pl.DataFrame
        The loaded PBDB data.
    """
    global _cached_pbdb_df
    if _cached_pbdb_df is None:
        data_path = Path(__file__).parent.parent / "data" / "pbdb_essential_taxonomy_with_refs.parquet"
        _cached_pbdb_df = pl.read_parquet(str(data_path))
    return _cached_pbdb_df


def query_zoobank_api(organism_name: str) -> dict | None:
    """
    Query ZooBank API for a given organism.

    Parameters
    ----------
    organism_name : str
        The scientific name of the organism to look up.

    Returns
    -------
    dict | None
        Dictionary containing publication info from ZooBank, or None if not found.
    """
    try:
        # ZooBank name search endpoint
        search_url = "https://zoobank.org/NomenclatorZoologicus/api/name/search"

        # Try exact match first
        params = {
            "name": organism_name,
            "exact": "true",
            "format": "json"
        }

        response = requests.get(search_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data and isinstance(data, list) and len(data) > 0:
            # Take first match
            record = data[0]

            # Extract relevant information
            return {
                "nam": record.get("name", organism_name),
                "att": record.get("authorship", NOT_AVAILABLE),
                "ref": record.get("original_publication", NOT_AVAILABLE),
                "aut": record.get("authorship_authors", NOT_AVAILABLE),
                "pby": record.get("authorship_year", NOT_AVAILABLE),
                "doi": record.get("doi", NOT_AVAILABLE),
                "zoobank_id": record.get("lsid", NOT_AVAILABLE),
                "source": "ZooBank"
            }

        return None

    except Exception as e:
        print(f"ZooBank API error: {e}")
        return None


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
    words = ref_text.split()
    for word in words:
        # clean word of punctuation and check if it's a valid year
        clean_word = word.strip(".,();:-")
        if (clean_word.isdigit() and len(clean_word) == 4 and
            (clean_word.startswith("17") or clean_word.startswith("18") or
             clean_word.startswith("19") or clean_word.startswith("20"))):
            year_num = int(clean_word)
            if 1700 <= year_num <= 2029:
                return clean_word
    return NOT_AVAILABLE


def query_pbdb_fallback(organism_name: str) -> dict | None:
    """
    Query local PBDB dataset as fallback when ZooBank fails.

    Parameters
    ----------
    organism_name : str
        The scientific name of the organism to look up.

    Returns
    -------
    dict | None
        Dictionary containing publication info, or None if not found.
    """
    try:
        df = load_pbdb_data_fallback()

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

        # get DOI from dataset if available
        doi = record.get("doi", [NOT_AVAILABLE])[0] if "doi" in record else NOT_AVAILABLE
        if doi == "null" or doi is None:
            doi = NOT_AVAILABLE

        return {
            "nam": nam,
            "att": att,
            "ref": ref,
            "aut": ref_author,  # author from reference
            "pby": ref_year,    # publication year from reference
            "doi": doi,  # DOI from dataset
            "source": "PBDB Dataset"
        }

    except Exception as e:
        return {"error": f"PBDB fallback query error: {e}", "organism": organism_name}


def query_species_info(organism_name: str) -> dict | None:
    """
    Query species information, trying ZooBank first, then PBDB fallback.

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
    print(f"Querying ZooBank for: {organism_name}")

    # Try ZooBank first
    zoobank_result = query_zoobank_api(organism_name)

    if zoobank_result:
        print(f"Found in ZooBank: {organism_name}")
        return zoobank_result

    # Fallback to PBDB dataset
    print(f"ZooBank failed, trying PBDB dataset for: {organism_name}")
    pbdb_result = query_pbdb_fallback(organism_name)

    if pbdb_result:
        print(f"Found in PBDB dataset: {organism_name}")
        return pbdb_result

    return None


def query_multiple_species(
    species_list: list[str],
) -> tuple[list[dict], list[str], list[dict]]:
    """
    Query multiple species with ZooBank/PBDB fallback.

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
        record = query_species_info(species.strip())

        if record is None:
            not_found.append(species)
        elif "error" in record:
            errors.append({  "organism": species, "error": record["error"]})
        else:
            results.append(record)

    return results, not_found, errors