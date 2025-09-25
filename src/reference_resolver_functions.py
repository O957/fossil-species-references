"""
Reference resolver for finding original taxonomic
authority publications. This module provides fallback
mechanisms to locate original describing papers when
they're not available in PBDB using function-based
approach.
"""

import json
import re
from pathlib import Path

import requests

# cache configuration
CACHE_DIR = Path.home() / ".cache" / "fossil_references"
CACHE_FILE = CACHE_DIR / "reference_cache.json"

# api configuration
CROSSREF_BASE_URL = "https://api.crossref.org/works"
BHL_BASE_URL = "https://www.biodiversitylibrary.org/api3"
WORMS_BASE_URL = "https://www.marinespecies.org/rest"
GBIF_BASE_URL = "https://api.gbif.org/v1"


def load_reference_cache() -> dict:
    """
    Load reference cache from disk.

    Returns
    -------
    dict
        Cached references.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_reference_cache(cache: dict):
    """
    Save reference cache to disk.

    Parameters
    ----------
    cache : dict
        Cache dictionary to save.
    """
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
    Optional[dict]
        Cached reference or None.
    """
    cache = load_reference_cache()
    return cache.get(key)


def cache_reference(key: str, reference_data: dict):
    """
    Cache a reference.

    Parameters
    ----------
    key : str
        Cache key.
    reference_data : dict
        Reference data to cache.
    """
    cache = load_reference_cache()
    cache[key] = reference_data
    save_reference_cache(cache)


def extract_title_from_pbdb_reference(pbdb_reference: str) -> str:
    """
    Extract the paper title from a PBDB reference string.

    Parameters
    ----------
    pbdb_reference : str
        Full PBDB reference text.

    Returns
    -------
    str
        Extracted title or empty string.
    """
    # typical PBDB format: "Author. Year. Title. Journal info"
    # but sometimes: "Author Year. Title. Journal info"

    # find the year pattern and extract title after it
    year_pattern = (
        r"(\d{4})\.\s*(.+?)(?:\.\s*[A-Z][^.]*|\s+\d+:|\s+\d+\(\d+\)|$)"
    )
    match = re.search(year_pattern, pbdb_reference)

    if match:
        title_part = match.group(2).strip()
        # clean up common title endings
        title_part = title_part.replace(" /", "").strip()
        # remove trailing periods
        title_part = title_part.rstrip(".")
        return title_part

    # fallback: try simple split approach
    parts = pbdb_reference.split(". ")
    if len(parts) >= 3:
        title_part = parts[2].strip()
        title_part = title_part.replace(" /", "").strip().rstrip(".")
        return title_part

    return ""


def search_crossref_by_title(
    title: str, author_name: str = "", year: str = ""
) -> dict | None:
    """
    Search CrossRef for a specific paper by title.

    Parameters
    ----------
    title : str
        Paper title to search for.
    author_name : str
        Optional author name for additional filtering.
    year : str
        Optional year for additional filtering.

    Returns
    -------
    Optional[dict]
        Reference data if found, None otherwise.
    """
    if not title or len(title.strip()) < 10:
        return None

    # clean title for search
    title_clean = title.strip()

    params = {
        "query": f'"{title_clean}"',  # exact phrase search
        "rows": 10,
    }

    # add year filter if provided
    if year:
        params["filter"] = f"from-pub-date:{year},until-pub-date:{year}"

    try:
        response = requests.get(CROSSREF_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("message", {}).get("items"):
            for item in data["message"]["items"]:
                item_title = (item.get("title", [""])[0] or "").lower()
                search_title = title_clean.lower()

                # check for title similarity - be more flexible with case and partial matches
                # normalize both titles for comparison
                search_words = set(search_title.replace("-", " ").split())
                item_words = set(item_title.replace("-", " ").split())

                # remove very common words
                common = {
                    "the",
                    "a",
                    "an",
                    "of",
                    "in",
                    "on",
                    "and",
                    "or",
                    "for",
                    "from",
                    "to",
                    "by",
                    "with",
                }
                search_words = {
                    w for w in search_words if w not in common and len(w) > 2
                }
                item_words = {
                    w for w in item_words if w not in common and len(w) > 2
                }

                # check if significant overlap exists
                if search_words and item_words:
                    overlap = len(search_words & item_words)
                    if overlap >= min(
                        3, len(search_words) * 0.5
                    ):  # at least 3 words or 50% match
                        # additional author validation if provided
                        if author_name:
                            authors = item.get("author", [])
                            author_clean = (
                                re.sub(r"[()0-9]", "", author_name)
                                .strip()
                                .lower()
                            )
                            if not any(
                                author_clean in auth.get("family", "").lower()
                                for auth in authors
                            ):
                                continue

                        return {
                            "title": item.get("title", ["Unknown"])[0],
                            "authors": [
                                f"{a.get('given', '')} {a.get('family', '')}".strip()
                                for a in item.get("author", [])
                            ],
                            "year": str(
                                item.get("published-print", {}).get(
                                    "date-parts", [[year or "Unknown"]]
                                )[0][0]
                            ),
                            "journal": item.get("container-title", [""])[0]
                            if item.get("container-title")
                            else None,
                            "volume": item.get("volume"),
                            "pages": item.get("page"),
                            "doi": item.get("DOI"),
                            "url": item.get("URL"),
                            "source": "CrossRef",
                        }
    except Exception as e:
        print(f"CrossRef title search error: {e}")

    return None


def search_crossref(
    author_name: str, year: str, taxon_name: str = ""
) -> dict | None:
    """
    Search CrossRef for academic references.

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
    Optional[dict]
        Reference data if found, None otherwise.
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
        response = requests.get(CROSSREF_BASE_URL, params=params, timeout=10)
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
                    return {
                        "title": item.get("title", ["Unknown"])[0],
                        "authors": [
                            f"{a.get('given', '')} {a.get('family', '')}".strip()
                            for a in authors
                        ],
                        "year": str(
                            item.get("published-print", {}).get(
                                "date-parts", [[year]]
                            )[0][0]
                        ),
                        "journal": item.get("container-title", [""])[0]
                        if item.get("container-title")
                        else None,
                        "volume": item.get("volume"),
                        "pages": item.get("page"),
                        "doi": item.get("DOI"),
                        "url": item.get("URL"),
                        "source": "CrossRef",
                    }
    except Exception as e:
        print(f"CrossRef search error: {e}")

    return None


def search_bhl(
    author_name: str, year: str, api_key: str = None
) -> dict | None:
    """
    Search Biodiversity Heritage Library for historical references.

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
    Optional[dict]
        Reference data if found, None otherwise.
    """
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
            return {
                "title": result.get("Title", "Unknown"),
                "authors": [author_clean],
                "year": year,
                "journal": result.get("PublisherName"),
                "volume": None,
                "pages": None,
                "doi": None,
                "url": result.get("BHLUrl"),
                "source": "BHL",
            }
    except Exception as e:
        print(f"BHL search error: {e}")

    return None


def search_worms(taxon_name: str) -> dict | None:
    """
    Search World Register of Marine Species for marine taxa.

    Parameters
    ----------
    taxon_name : str
        Scientific name of the taxon.

    Returns
    -------
    Optional[dict]
        Reference data if found, None otherwise.
    """
    try:
        # first, get the AphiaID for the taxon
        params = {"scientificname": taxon_name}
        response = requests.get(
            f"{WORMS_BASE_URL}/AphiaRecordsByName", params=params, timeout=10
        )
        response.raise_for_status()
        records = response.json()

        if records and len(records) > 0:
            aphia_id = records[0].get("AphiaID")
            authority = records[0].get("authority", "")

            # parse authority for year
            year_match = re.search(r"\b(1[789]\d{2}|20[012]\d)\b", authority)
            year = year_match.group(1) if year_match else None

            # get detailed record
            detail_response = requests.get(
                f"{WORMS_BASE_URL}/AphiaRecordByAphiaID/{aphia_id}", timeout=10
            )
            detail_response.raise_for_status()
            detail = detail_response.json()

            # extract reference if available
            if detail.get("citation"):
                return {
                    "title": detail.get("citation", "Unknown"),
                    "authors": [
                        authority.replace(year, "").strip()
                        if year
                        else authority
                    ],
                    "year": year or "Unknown",
                    "journal": None,
                    "volume": None,
                    "pages": None,
                    "doi": None,
                    "url": None,
                    "source": "WoRMS",
                }
    except Exception as e:
        print(f"WoRMS search error: {e}")

    return None


def is_marine_taxon(taxon_name: str) -> bool:
    """
    Check if taxon is likely marine based on name.

    Parameters
    ----------
    taxon_name : str
        Scientific name.

    Returns
    -------
    bool
        True if likely marine.
    """
    marine_indicators = [
        "shark",
        "ray",
        "fish",
        "coral",
        "squalicorax",
        "enchodus",
        "mosasaur",
        "plesiosaur",
        "ichthyosaur",
    ]
    return any(
        indicator in taxon_name.lower() for indicator in marine_indicators
    )


def resolve_reference_by_title(
    pbdb_reference: str,
    authority: str,
    year: str = None,
    use_cache: bool = True,
) -> dict | None:
    """
    Search for the specific paper referenced in PBDB by title.

    Parameters
    ----------
    pbdb_reference : str
        The full PBDB reference text.
    authority : str
        Taxonomic authority (for author extraction).
    year : str
        Optional year if already extracted.
    use_cache : bool
        Whether to use caching.

    Returns
    -------
    Optional[dict]
        The resolved reference or None.
    """
    # extract title from PBDB reference
    title = extract_title_from_pbdb_reference(pbdb_reference)
    if not title:
        return None

    # create cache key based on title
    cache_key = f"title:{title}"

    # check cache first
    if use_cache:
        cached = get_cached_reference(cache_key)
        if cached:
            return cached

    # extract year if not provided
    if not year:
        year_match = re.search(r"\b(1[789]\d{2}|20[012]\d)\b", authority)
        year = year_match.group(1) if year_match else None

    # extract author name (remove year and "et al.")
    author_name = re.sub(r"\b\d{4}\b", "", authority).strip()
    author_name = author_name.replace("et al.", "").strip()

    # search CrossRef by title
    result = search_crossref_by_title(title, author_name, year)

    # cache successful result
    if result and use_cache:
        cache_reference(cache_key, result)

    return result


def resolve_reference(
    taxon_name: str,
    authority: str,
    year: str = None,
    bhl_api_key: str = None,
    use_cache: bool = True,
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
    bhl_api_key : str
        Optional BHL API key.
    use_cache : bool
        Whether to use caching.

    Returns
    -------
    Optional[dict]
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

    # extract author name (remove year and "et al.")
    author_name = re.sub(r"\b\d{4}\b", "", authority).strip()
    author_name = author_name.replace("et al.", "").strip()

    # try different sources in order of preference
    result = None

    # 1. Try CrossRef (good for recent papers)
    result = search_crossref(author_name, year, taxon_name)

    # 2. For marine species, try WoRMS
    if not result and is_marine_taxon(taxon_name):
        result = search_worms(taxon_name)

    # 3. For older references, try BHL
    if not result and int(year) < 1950:
        result = search_bhl(author_name, year, bhl_api_key)

    # cache successful result
    if result and use_cache:
        # clean result before caching (remove any confidence field)
        clean_result = {k: v for k, v in result.items() if k != "confidence"}
        cache_reference(cache_key, clean_result)

    return result


def validate_reference_match(
    pbdb_reference: str, external_reference: dict, attribution_mismatch: bool
) -> bool:
    """
    Validate if external reference matches the PBDB reference when there's no mismatch.

    Parameters
    ----------
    pbdb_reference : str
        The full PBDB reference text.
    external_reference : dict
        External reference data.
    attribution_mismatch : bool
        Whether there's a mismatch between authority and PBDB reference.

    Returns
    -------
    bool
        True if the external reference is valid to show.
    """
    # always show external references when there's a mismatch
    # (external is likely the missing original)
    if attribution_mismatch:
        return True

    # when no mismatch, validate that external reference matches PBDB reference
    if not external_reference:
        return False

    pbdb_lower = pbdb_reference.lower()
    ext_title = (external_reference.get("title") or "").lower()
    ext_journal = (external_reference.get("journal") or "").lower()

    # check if external reference title appears in PBDB reference
    if ext_title and len(ext_title.strip()) > 10:  # ignore very short titles
        # remove common words and check for substantial overlap
        ext_title_words = set(ext_title.split())
        pbdb_words = set(pbdb_lower.split())

        # remove common words
        common_words = {
            "the",
            "a",
            "an",
            "of",
            "in",
            "on",
            "and",
            "or",
            "for",
            "with",
            "by",
        }
        ext_title_words -= common_words
        pbdb_words -= common_words

        # check for significant word overlap (at least 40% of title words)
        if (
            ext_title_words
            and len(ext_title_words & pbdb_words) / len(ext_title_words) >= 0.4
        ):
            return True

    # check if journal names match
    if ext_journal and ext_journal in pbdb_lower:
        return True

    # check if external title is contained in PBDB reference
    if ext_title and ext_title in pbdb_lower:
        return True

    # if we can't validate the match, don't show it to avoid confusion
    return False


def format_reference_citation(ref_data: dict) -> str:
    """
    Format a reference as a citation string.

    Parameters
    ----------
    ref_data : dict
        Reference data dictionary.

    Returns
    -------
    str
        Formatted citation.
    """
    parts = []

    # authors
    authors = ref_data.get("authors", [])
    if authors:
        if len(authors) > 2:
            parts.append(f"{authors[0]} et al.")
        else:
            parts.append(", ".join(authors))

    # year
    parts.append(f"{ref_data.get('year', 'Unknown')}.")

    # title
    parts.append(ref_data.get("title", "Unknown title"))

    # journal info
    if ref_data.get("journal"):
        journal_part = ref_data["journal"]
        if ref_data.get("volume"):
            journal_part += f" {ref_data['volume']}"
        if ref_data.get("pages"):
            journal_part += f":{ref_data['pages']}"
        parts.append(journal_part)

    return " ".join(parts)
