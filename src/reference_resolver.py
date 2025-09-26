"""
Reference resolver for finding original taxonomic authority publications.
This module provides fallback mechanisms to locate original describing
papers when they're not available in PBDB.
"""

import json
import re
from pathlib import Path

import requests

from config_loader import (
    BHL_BASE_URL,
    CACHE_DIR_NAME,
    CACHE_FILE_NAME,
    CACHE_SUBDIR_NAME,
    CROSSREF_BASE_URL,
    WORMS_BASE_URL,
)

# cache configuration
CACHE_DIR = Path.home() / CACHE_DIR_NAME / CACHE_SUBDIR_NAME
CACHE_FILE = CACHE_DIR / CACHE_FILE_NAME


def create_reference_result(
    title: str,
    authors: list[str],
    year: str,
    journal: str | None = None,
    volume: str | None = None,
    pages: str | None = None,
    doi: str | None = None,
    url: str | None = None,
    source: str = "unknown",
    confidence: float = 0.0,
) -> dict:
    """
    Create a reference result dictionary.

    Parameters
    ----------
    title : str
        Title of the reference.
    authors : list[str]
        List of author names.
    year : str
        Publication year.
    journal : str | None
        Journal name.
    volume : str | None
        Volume number.
    pages : str | None
        Page numbers.
    doi : str | None
        DOI string.
    url : str | None
        URL link.
    source : str
        Source of the reference.
    confidence : float
        Confidence score.

    Returns
    -------
    dict
        Reference result dictionary.
    """
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "volume": volume,
        "pages": pages,
        "doi": doi,
        "url": url,
        "source": source,
        "confidence": confidence,
    }


def load_cache() -> dict:
    """
    Load reference cache from disk.

    Returns
    -------
    dict
        Cache dictionary.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_cache(cache: dict):
    """
    Save reference cache to disk.

    Parameters
    ----------
    cache : dict
        Cache dictionary to save.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_cached_reference(key: str) -> dict | None:
    """
    Get cached reference by key.

    Parameters
    ----------
    key : str
        Cache key.

    Returns
    -------
    dict | None
        Cached reference or None.
    """
    cache = load_cache()
    return cache.get(key)


def cache_reference(key: str, value: dict):
    """
    Cache a reference.

    Parameters
    ----------
    key : str
        Cache key.
    value : dict
        Reference data to cache.
    """
    cache = load_cache()
    cache[key] = value
    save_cache(cache)


def search_crossref(
    author_name: str, year: str, taxon_name: str = ""
) -> dict | None:
    """
    Search CrossRef for a reference.

    Parameters
    ----------
    author_name : str
        Author name (e.g., "Whitley").
    year : str
        Publication year.
    taxon_name : str
        Optional taxon name to refine search.

    Returns
    -------
    dict | None
        Reference if found, None otherwise.
    """
    # clean author name (remove parentheses, year if present)
    author_clean = re.sub(r"[()0-9]", "", author_name).strip()

    # build query
    query_parts = [author_clean]
    if taxon_name:
        # add genus name for better matching
        genus = taxon_name.split()[0] if " " in taxon_name else taxon_name
        query_parts.append(genus)

    params = {
        "query": " ".join(query_parts),
        "filter": f"from-pub-date:{year},until-pub-date:{year}",
        "rows": 5,
    }

    try:
        response = requests.get(
            CROSSREF_BASE_URL, params=params, timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get("message", {}).get("items"):
            for item in data["message"]["items"]:
                # check if author matches
                authors = item.get("author", [])
                if any(
                    author_clean.lower() in auth.get("family", "").lower()
                    for auth in authors
                ):
                    return create_reference_result(
                        title=item.get("title", ["Unknown"])[0],
                        authors=[
                            f"{a.get('given', '')} {a.get('family', '')}".strip()
                            for a in authors
                        ],
                        year=str(
                            item.get("published-print", {}).get(
                                "date-parts", [[year]]
                            )[0][0]
                        ),
                        journal=item.get("container-title", [""])[0]
                        if item.get("container-title")
                        else None,
                        volume=item.get("volume"),
                        pages=item.get("page"),
                        doi=item.get("DOI"),
                        url=item.get("URL"),
                        source="CrossRef",
                        confidence=0.8,
                    )
    except Exception as e:
        print(f"CrossRef search error: {e}")

    return None


def search_bhl(
    author_name: str, year: str, api_key: str = None
) -> dict | None:
    """
    Search BHL for a reference.

    Parameters
    ----------
    author_name : str
        Author name.
    year : str
        Publication year.
    api_key : str
        Optional BHL API key for better rate limits.

    Returns
    -------
    dict | None
        Reference if found, None otherwise.
    """
    # note: BHL API requires registration for a key
    # this is a simplified example
    author_clean = re.sub(r"[()0-9]", "", author_name).strip()

    params = {
        "op": "PublicationSearch",
        "searchterm": f"{author_clean} {year}",
        "format": "json",
    }

    if api_key:
        params["apikey"] = api_key

    try:
        response = requests.get(
            f"{BHL_BASE_URL}/query", params=params, timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # parse BHL response (simplified)
        if data.get("Status") == "ok" and data.get("Result"):
            result = data["Result"][0]  # take first match
            return create_reference_result(
                title=result.get("Title", "Unknown"),
                authors=[author_clean],
                year=year,
                journal=result.get("PublisherName"),
                url=result.get("BHLUrl"),
                source="BHL",
                confidence=0.7,
            )
    except Exception as e:
        print(f"BHL search error: {e}")

    return None


def search_worms(taxon_name: str) -> dict | None:
    """
    Search WoRMS for taxonomic reference.

    Parameters
    ----------
    taxon_name : str
        Scientific name of the taxon.

    Returns
    -------
    dict | None
        Reference if found, None otherwise.
    """
    try:
        # first, get the AphiaID for the taxon
        params = {"scientificname": taxon_name}
        response = requests.get(
            f"{WORMS_BASE_URL}/AphiaRecordsByName",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        records = response.json()

        if records and len(records) > 0:
            aphia_id = records[0].get("AphiaID")
            authority = records[0].get("authority", "")

            # parse authority for year
            year_match = re.search(
                r"\b(1[789]\d{2}|20[012]\d)\b", authority
            )
            year = year_match.group(1) if year_match else None

            # get detailed record
            detail_response = requests.get(
                f"{WORMS_BASE_URL}/AphiaRecordByAphiaID/{aphia_id}",
                timeout=10,
            )
            detail_response.raise_for_status()
            detail = detail_response.json()

            # extract reference if available
            if detail.get("citation"):
                return create_reference_result(
                    title=detail.get("citation", "Unknown"),
                    authors=[
                        authority.replace(year, "").strip()
                        if year
                        else authority
                    ],
                    year=year or "Unknown",
                    source="WoRMS",
                    confidence=0.9,
                )
    except Exception as e:
        print(f"WoRMS search error: {e}")

    return None


def resolve_reference_main(
    taxon_name: str,
    authority: str,
    year: str = None,
    use_cache: bool = True,
    bhl_api_key: str = None
) -> dict | None:
    """
    Attempt to resolve the original reference for a taxonomic authority.

    Parameters
    ----------
    taxon_name : str
        Scientific name of the taxon.
    authority : str
        Taxonomic authority (e.g., "Whitley 1939").
    year : str
        Optional year if already extracted.
    use_cache : bool
        Whether to use caching.
    bhl_api_key : str
        Optional BHL API key.

    Returns
    -------
    dict | None
        The resolved reference or None.
    """
    # create cache key
    cache_key = f"{taxon_name}:{authority}"

    # check cache first
    if use_cache:
        cached = get_cached_reference(cache_key)
        if cached:
            return cached

    # extract year if not provided
    if not year:
        year_match = re.search(r"\b(1[789]\d{2}|20[012]\d)\b", authority)
        year = year_match.group(1) if year_match else None

    if not year:
        return None

    # extract author name
    author_name = re.sub(r"\b\d{4}\b", "", authority).strip()

    # try different sources in order of preference
    result = None

    # 1. Try CrossRef (good for recent papers)
    result = search_crossref(author_name, year, taxon_name)

    # 2. For marine species, try WoRMS
    if not result and any(
        marine_indicator in taxon_name.lower()
        for marine_indicator in ["shark", "ray", "fish", "coral"]
    ):
        result = search_worms(taxon_name)

    # 3. For older references, try BHL
    if not result and int(year) < 1950:
        result = search_bhl(author_name, year, bhl_api_key)

    # cache successful result
    if result and use_cache:
        cache_reference(cache_key, result)

    return result


def format_reference_citation(ref: dict) -> str:
    """
    Format a reference result as a citation string.

    Parameters
    ----------
    ref : dict
        The reference to format.

    Returns
    -------
    str
        Formatted citation.
    """
    parts = []

    # authors
    if ref.get("authors"):
        if len(ref["authors"]) > 2:
            parts.append(f"{ref['authors'][0]} et al.")
        else:
            parts.append(", ".join(ref["authors"]))

    # year
    parts.append(f"{ref.get('year', 'Unknown')}.")

    # title
    parts.append(ref.get("title", "Unknown title"))

    # journal info
    if ref.get("journal"):
        journal_part = ref["journal"]
        if ref.get("volume"):
            journal_part += f" {ref['volume']}"
        if ref.get("pages"):
            journal_part += f":{ref['pages']}"
        parts.append(journal_part)

    return " ".join(parts)
