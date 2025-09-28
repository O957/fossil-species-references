"""
Simplified database query functions for taxonomic information.
"""

import re
import time
from pathlib import Path
from typing import Any

import polars as pl
import requests

from config_loader import API_DELAY, CROSSREF_BASE_URL, NOT_AVAILABLE


def extract_year(text: str) -> int | None:
    """
    Extract a 4-digit year from text.

    Parameters
    ----------
    text : str
        Text containing a year.

    Returns
    -------
    Optional[int]
        Extracted year or None.
    """
    if not text or text == NOT_AVAILABLE:
        return None

    # look for 4-digit years
    years = re.findall(r"\b(1[7-9]\d{2}|20[0-2]\d)\b", text)
    if years:
        return int(years[0])
    return None


def extract_author(text: str) -> str:
    """
    Extract author from authority string.

    Parameters
    ----------
    text : str
        Authority string like "Cope, 1874" or "(Cope, 1874)".

    Returns
    -------
    str
        Extracted author name.
    """
    if not text or text == NOT_AVAILABLE:
        return NOT_AVAILABLE

    # remove parentheses and year
    clean = text.replace("(", "").replace(")", "").strip()

    # split and remove year-like tokens
    parts = clean.split()
    author_parts = []
    for part in parts:
        # skip if it looks like a year
        if not (part.isdigit() and len(part) == 4):
            author_parts.append(part.rstrip(","))

    return " ".join(author_parts) if author_parts else NOT_AVAILABLE


def extract_paper_title(citation: str) -> str:
    """
    Extract paper title from a full citation.

    Parameters
    ----------
    citation : str
        Full citation string.

    Returns
    -------
    str
        Extracted paper title or original citation if extraction fails.
    """
    if not citation or citation == NOT_AVAILABLE:
        return NOT_AVAILABLE

    # handle common citation formats:
    # "Author. Year. Title. Journal..."
    # "Author (Year). Title. Journal..."
    # "Author, Year. Title. Journal..."

    # look for patterns with year followed by title
    parts = citation.split(". ")

    if len(parts) >= 3:
        # check each part for a year pattern
        for i, part in enumerate(parts):
            # if this part contains a 4-digit year, next part might be title
            if re.search(r"\b(1[7-9]\d{2}|20[0-2]\d)\b", part) and i + 1 < len(
                parts
            ):
                title_candidate = parts[i + 1].strip()

                # clean up title - remove trailing punctuation and journal info
                title = title_candidate

                # stop at common journal indicators
                journal_indicators = [
                    "in ",
                    "journal",
                    "bulletin",
                    "proceedings",
                    "annals",
                    "transactions",
                    "memoirs",
                    "reports",
                    "vol.",
                    "volume",
                ]

                for indicator in journal_indicators:
                    if indicator in title.lower():
                        title = title[: title.lower().find(indicator)].strip()
                        break

                # clean trailing punctuation
                title = title.rstrip(".,;:")

                if title and len(title) > 5:  # reasonable title length
                    return title

    # fallback: if no clear pattern, return first 100 chars
    if len(citation) > 100:
        return citation[:100] + "..."

    return citation


def query_gbif(species_name: str) -> dict[str, Any] | None:
    """
    Query GBIF for taxonomic information.

    Parameters
    ----------
    species_name : str
        Species name to search.

    Returns
    -------
    Optional[Dict[str, Any]]
        Taxonomic information or None.
    """
    try:
        base_url = "https://api.gbif.org/v1"
        match_url = f"{base_url}/species/match"
        params = {"name": species_name, "strict": False}

        response = requests.get(match_url, params=params, timeout=5)
        response.raise_for_status()
        match_data = response.json()

        if match_data.get("matchType") != "NONE":
            usage_key = match_data.get("usageKey")
            if usage_key:
                # get full record
                detail_url = f"{base_url}/species/{usage_key}"
                detail_response = requests.get(detail_url, timeout=5)
                detail_response.raise_for_status()
                detail_data = detail_response.json()

                authorship = detail_data.get("authorship", NOT_AVAILABLE)
                published_in = detail_data.get("publishedIn", NOT_AVAILABLE)

                # GBIF often has the reference in publishedIn field
                reference = (
                    published_in
                    if published_in != NOT_AVAILABLE
                    else NOT_AVAILABLE
                )

                return {
                    "taxonomic_authority": authorship,
                    "reference": reference,
                    "year": extract_year(authorship),
                    "author": extract_author(authorship),
                    "doi": NOT_AVAILABLE,
                    "source": "GBIF",
                }
    except Exception as e:
        print(f"GBIF error: {e}")

    return None


def query_zoobank(species_name: str) -> dict[str, Any] | None:
    """
    Query ZooBank for taxonomic information.

    Parameters
    ----------
    species_name : str
        Species name to search.

    Returns
    -------
    Optional[Dict[str, Any]]
        Taxonomic information or None.
    """
    try:
        search_url = (
            "https://zoobank.org/NomenclatorZoologicus/api/name/search"
        )
        params = {"name": species_name, "exact": "true", "format": "json"}

        response = requests.get(search_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data and isinstance(data, list) and len(data) > 0:
            record = data[0]
            authorship = record.get("authorship", NOT_AVAILABLE)
            return {
                "taxonomic_authority": authorship,
                "reference": record.get("original_publication", NOT_AVAILABLE),
                "year": extract_year(record.get("authorship_year", "")),
                "author": extract_author(authorship),
                "doi": record.get("doi", NOT_AVAILABLE),
                "source": "ZooBank",
            }
    except:
        pass

    return None


def query_pbdb_local(species_name: str) -> dict[str, Any] | None:
    """
    Query local PBDB parquet file.

    Parameters
    ----------
    species_name : str
        Species name to search.

    Returns
    -------
    Optional[Dict[str, Any]]
        Taxonomic information or None.
    """
    try:
        pbdb_file = (
            Path(__file__).parent.parent
            / "data"
            / "pbdb_essential_taxonomy_with_refs.parquet"
        )
        if not pbdb_file.exists():
            return None

        df = pl.read_parquet(str(pbdb_file))

        # search for exact match (case-insensitive)
        result = df.filter(
            pl.col("nam").str.to_lowercase() == species_name.lower()
        )

        if not result.is_empty():
            row = result.to_dicts()[0]
            att = row.get("att", NOT_AVAILABLE)
            full_reference = row.get("ref", NOT_AVAILABLE)

            # extract author from authority or reference
            author = extract_author(att)
            if author == NOT_AVAILABLE and full_reference != NOT_AVAILABLE:
                # try to extract from reference (e.g., "E. D. Cope. 1874. ...")
                parts = full_reference.split(".")
                if parts:
                    author = parts[0].strip()

            # extract year from authority
            year = extract_year(att)

            return {
                "taxonomic_authority": att,
                "reference": full_reference,  # complete citation as it appears
                "year": year,
                "author": author,
                "doi": row.get("doi", NOT_AVAILABLE)
                if row.get("doi") not in ["null", None]
                else NOT_AVAILABLE,
                "source": "PBDB",
            }
    except Exception as e:
        print(f"Error querying PBDB: {e}")

    return None


def query_worms(species_name: str) -> dict[str, Any] | None:
    """
    Query WoRMS for marine species information.

    Parameters
    ----------
    species_name : str
        Species name to search.

    Returns
    -------
    Optional[Dict[str, Any]]
        Taxonomic information or None.
    """
    try:
        from config_loader import WORMS_BASE_URL

        search_url = f"{WORMS_BASE_URL}/AphiaRecordsByMatchNames"
        params = {"scientificnames[]": species_name, "marine_only": "false"}

        response = requests.get(search_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data and isinstance(data, list) and data[0]:
            matches = data[0]
            if matches and isinstance(matches, list):
                record = matches[0]

                # get citation
                aphia_id = record.get("AphiaID")
                if aphia_id:
                    citation_url = (
                        f"{WORMS_BASE_URL}/AphiaRecordByAphiaID/{aphia_id}"
                    )
                    citation_response = requests.get(citation_url, timeout=5)
                    citation_response.raise_for_status()
                    full_record = citation_response.json()

                    authority = full_record.get("authority", NOT_AVAILABLE)
                    return {
                        "taxonomic_authority": authority,
                        "reference": full_record.get(
                            "citation", NOT_AVAILABLE
                        ),
                        "year": extract_year(authority),
                        "author": extract_author(authority),
                        "doi": NOT_AVAILABLE,
                        "source": "WoRMS",
                    }
    except:
        pass

    return None


def query_crossref(
    reference: str, author: str = None, year: int = None
) -> dict[str, str] | None:
    """
    Query CrossRef for publication DOI and link.

    Parameters
    ----------
    reference : str
        Publication reference/title to search for.
    author : str
        Optional author name.
    year : int
        Optional publication year.

    Returns
    -------
    Optional[Dict[str, str]]
        Dictionary with doi and paper_link, or None.
    """
    if not reference or reference == NOT_AVAILABLE:
        return None

    try:
        # extract title from reference if it contains full citation
        # e.g., "E. D. Cope. 1874. Review of the Vertebrata..." -> "Review of the Vertebrata..."
        title = reference
        if ". " in reference and reference[0].isupper():
            # likely a full citation, extract title part
            parts = reference.split(". ")
            for i, part in enumerate(parts):
                # title usually comes after year
                if i > 0 and any(char.isdigit() for char in parts[i - 1]):
                    # found likely title
                    title = part
                    # remove journal info if present
                    if " in " in title.lower() or " of " in title.lower():
                        title_parts = title.split(".")
                        if title_parts:
                            title = title_parts[0]
                    break

        # build query with just essential parts for old papers
        query_parts = []

        # add title
        if title:
            # clean up title - remove publication details
            clean_title = title.split(".")[0] if "." in title else title
            query_parts.append(clean_title)

        # add author and year for precision
        if author and author != NOT_AVAILABLE:
            query_parts.append(author)
        if year:
            query_parts.append(str(year))

        query = " ".join(query_parts)

        params = {
            "query": query,
            "rows": 10,  # increased for better chance of finding old papers
            "select": "DOI,URL,title,author,published-print,published-online",
        }

        response = requests.get(
            CROSSREF_BASE_URL,
            params=params,
            timeout=10,  # increased timeout
        )
        response.raise_for_status()
        data = response.json()

        if data.get("message", {}).get("items"):
            # find best match
            for item in data["message"]["items"]:
                item_title = " ".join(item.get("title", []))

                # for old papers, be more lenient with matching
                title_lower = title.lower()
                item_title_lower = item_title.lower()

                # check various matching strategies
                title_words = set(
                    title_lower.split()[:5]
                )  # first 5 words of title
                item_words = set(item_title_lower.split())

                # if significant overlap in words, consider it a match
                if len(title_words & item_words) >= min(3, len(title_words)):
                    doi = item.get("DOI", NOT_AVAILABLE)
                    url = item.get("URL")

                    if not url and doi != NOT_AVAILABLE:
                        url = f"https://doi.org/{doi}"

                    return {"doi": doi, "paper_link": url or NOT_AVAILABLE}
    except Exception as e:
        print(f"CrossRef error: {e}")

    return None


def search_taxonomy(species_name: str) -> dict[str, Any]:
    """
    Search for taxonomic information across databases.
    Searches all databases to find the most complete information,
    especially the reference paper that matches the taxonomic authority year.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.

    Returns
    -------
    Dict[str, Any]
        Search results with taxonomic authority, reference, DOI, etc.
    """
    # prepare result template
    result = {
        "search_term": species_name.strip(),
        "taxonomic_authority": NOT_AVAILABLE,
        "year": None,
        "author": NOT_AVAILABLE,
        "reference": NOT_AVAILABLE,
        "doi": NOT_AVAILABLE,
        "paper_link": NOT_AVAILABLE,
        "source": NOT_AVAILABLE,
        "year_mismatch": False,  # flag for reference year not matching authority year
    }

    # sequential database search (GBIF first)
    databases = [
        ("GBIF", query_gbif),
        ("ZooBank", query_zoobank),
        ("PBDB", query_pbdb_local),
        ("WoRMS", query_worms),
    ]

    # collect all results from databases
    all_results = []
    for db_name, query_func in databases:
        db_result = query_func(species_name)
        if db_result:
            all_results.append(db_result)

        # small delay between API calls
        if db_name not in ["PBDB"]:  # no delay for local file
            time.sleep(API_DELAY)

    # if no results at all, return empty result
    if not all_results:
        return result

    # find best authority (prefer first non-empty one)
    for db_result in all_results:
        if (
            result["taxonomic_authority"] == NOT_AVAILABLE
            and db_result.get("taxonomic_authority") != NOT_AVAILABLE
        ):
            result["taxonomic_authority"] = db_result["taxonomic_authority"]
            result["year"] = db_result.get("year")
            result["author"] = db_result.get("author", NOT_AVAILABLE)
            result["source"] = db_result["source"]
            break

    # find best reference using smart prioritization - ONLY accept references with matching years
    valid_references = []
    mismatched_references = []

    for db_result in all_results:
        if db_result.get("reference") != NOT_AVAILABLE:
            ref = db_result["reference"]
            source = db_result["source"]

            # extract year from reference
            ref_year = extract_year(ref)

            # STRICT: only accept references where year matches authority year
            if result["year"] and ref_year == result["year"]:
                # this reference has the exact matching year - this is the original paper

                # score the reference quality
                score = 0

                # prioritize PBDB for paleontological data (usually has best original references)
                if source == "PBDB":
                    score += 1000

                # prioritize sources that aren't modern database citations
                ref_lower = ref.lower()
                if any(
                    indicator in ref_lower
                    for indicator in [
                        "accessed through",
                        "fishbase",
                        "world register",
                        "editors",
                        "database",
                    ]
                ):
                    score -= 500  # penalize modern database citations

                # prefer longer references (more complete bibliographic info)
                score += len(ref)

                valid_references.append(
                    {
                        "reference": ref,
                        "source": source,
                        "score": score,
                        "doi": db_result.get("doi", NOT_AVAILABLE)
                        if db_result.get("doi") not in [None, "null"]
                        else NOT_AVAILABLE,
                    }
                )
            else:
                # reference year doesn't match - this is NOT the original description
                mismatched_references.append(
                    {
                        "reference": ref,
                        "source": source,
                        "ref_year": ref_year,
                        "authority_year": result["year"],
                    }
                )

    # if we have valid (year-matched) references, use the best one
    if valid_references:
        # sort by score (descending) and choose the best
        best_ref_data = max(valid_references, key=lambda x: x["score"])

        result["reference"] = best_ref_data["reference"]
        # also update DOI if available
        if best_ref_data["doi"] != NOT_AVAILABLE:
            result["doi"] = best_ref_data["doi"]

        # update source to show where reference came from
        best_reference_source = best_ref_data["source"]
        if (
            result["source"] != best_reference_source
            and best_reference_source not in result["source"]
        ):
            result["source"] = (
                f"{result['source']} (ref: {best_reference_source})"
            )

    else:
        # no valid references found - all have year mismatches
        # do NOT save any reference, but flag the mismatch
        result["year_mismatch"] = True
        result["reference"] = NOT_AVAILABLE

    # if we have authority and reference, try to get DOI via CrossRef
    if result["reference"] != NOT_AVAILABLE and (
        result["doi"] == NOT_AVAILABLE or result["doi"] is None
    ):
        crossref_result = query_crossref(
            result["reference"], result["author"], result["year"]
        )

        if crossref_result:
            result["doi"] = crossref_result["doi"]
            result["paper_link"] = crossref_result["paper_link"]

    return result
