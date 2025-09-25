"""
Reference resolver for finding original taxonomic authority publications.
This module provides fallback mechanisms to locate original describing
papers when they're not available in PBDB.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import quote

import requests

# cache configuration
CACHE_DIR = Path.home() / ".cache" / "fossil_references"
CACHE_FILE = CACHE_DIR / "reference_cache.json"

# api configuration
CROSSREF_BASE_URL = "https://api.crossref.org/works"
BHL_BASE_URL = "https://www.biodiversitylibrary.org/api3"
WORMS_BASE_URL = "https://www.marinespecies.org/rest"
GBIF_BASE_URL = "https://api.gbif.org/v1"


@dataclass
class ReferenceResult:
    """
    Container for reference search results.
    """
    title: str
    authors: List[str]
    year: str
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    source: str = "unknown"
    confidence: float = 0.0


class ReferenceCache:
    """
    Simple file-based cache for reference lookups.
    """

    def __init__(self):
        """Initialize cache, creating directory if needed."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cache from disk."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f, indent=2)

    def get(self, key: str) -> Optional[dict]:
        """Get cached reference by key."""
        return self.cache.get(key)

    def set(self, key: str, value: dict):
        """Cache a reference."""
        self.cache[key] = value
        self._save_cache()


class CrossRefSearcher:
    """
    Search CrossRef for academic references.
    """

    @staticmethod
    def search(author_name: str, year: str, taxon_name: str = "") -> Optional[ReferenceResult]:
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
        Optional[ReferenceResult]
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
            "rows": 5
        }

        try:
            response = requests.get(CROSSREF_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("message", {}).get("items"):
                for item in data["message"]["items"]:
                    # check if author matches
                    authors = item.get("author", [])
                    if any(author_clean.lower() in auth.get("family", "").lower()
                           for auth in authors):

                        return ReferenceResult(
                            title=item.get("title", ["Unknown"])[0],
                            authors=[f"{a.get('given', '')} {a.get('family', '')}".strip()
                                   for a in authors],
                            year=str(item.get("published-print", {}).get("date-parts", [[year]])[0][0]),
                            journal=item.get("container-title", [""])[0] if item.get("container-title") else None,
                            volume=item.get("volume"),
                            pages=item.get("page"),
                            doi=item.get("DOI"),
                            url=item.get("URL"),
                            source="CrossRef",
                            confidence=0.8
                        )
        except Exception as e:
            print(f"CrossRef search error: {e}")

        return None


class BHLSearcher:
    """
    Search Biodiversity Heritage Library for historical references.
    """

    @staticmethod
    def search(author_name: str, year: str, api_key: str = None) -> Optional[ReferenceResult]:
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
        Optional[ReferenceResult]
            Reference if found, None otherwise.
        """
        # note: BHL API requires registration for a key
        # this is a simplified example
        author_clean = re.sub(r"[()0-9]", "", author_name).strip()

        params = {
            "op": "PublicationSearch",
            "searchterm": f"{author_clean} {year}",
            "format": "json"
        }

        if api_key:
            params["apikey"] = api_key

        try:
            response = requests.get(f"{BHL_BASE_URL}/query", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # parse BHL response (simplified)
            if data.get("Status") == "ok" and data.get("Result"):
                result = data["Result"][0]  # take first match
                return ReferenceResult(
                    title=result.get("Title", "Unknown"),
                    authors=[author_clean],
                    year=year,
                    journal=result.get("PublisherName"),
                    url=result.get("BHLUrl"),
                    source="BHL",
                    confidence=0.7
                )
        except Exception as e:
            print(f"BHL search error: {e}")

        return None


class WoRMSSearcher:
    """
    Search World Register of Marine Species for marine taxa.
    """

    @staticmethod
    def search(taxon_name: str) -> Optional[ReferenceResult]:
        """
        Search WoRMS for taxonomic reference.

        Parameters
        ----------
        taxon_name : str
            Scientific name of the taxon.

        Returns
        -------
        Optional[ReferenceResult]
            Reference if found, None otherwise.
        """
        try:
            # first, get the AphiaID for the taxon
            params = {"scientificname": taxon_name}
            response = requests.get(
                f"{WORMS_BASE_URL}/AphiaRecordsByName",
                params=params,
                timeout=10
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
                    f"{WORMS_BASE_URL}/AphiaRecordByAphiaID/{aphia_id}",
                    timeout=10
                )
                detail_response.raise_for_status()
                detail = detail_response.json()

                # extract reference if available
                if detail.get("citation"):
                    return ReferenceResult(
                        title=detail.get("citation", "Unknown"),
                        authors=[authority.replace(year, "").strip() if year else authority],
                        year=year or "Unknown",
                        source="WoRMS",
                        confidence=0.9
                    )
        except Exception as e:
            print(f"WoRMS search error: {e}")

        return None


class ReferenceResolver:
    """
    Main resolver that orchestrates multiple search strategies.
    """

    def __init__(self, use_cache: bool = True, bhl_api_key: str = None):
        """
        Initialize the reference resolver.

        Parameters
        ----------
        use_cache : bool
            Whether to use caching.
        bhl_api_key : str
            Optional BHL API key.
        """
        self.cache = ReferenceCache() if use_cache else None
        self.bhl_api_key = bhl_api_key

    def resolve(
        self,
        taxon_name: str,
        authority: str,
        year: str = None
    ) -> Optional[ReferenceResult]:
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

        Returns
        -------
        Optional[ReferenceResult]
            The resolved reference or None.
        """
        # create cache key
        cache_key = f"{taxon_name}:{authority}"

        # check cache first
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return ReferenceResult(**cached)

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
        result = CrossRefSearcher.search(author_name, year, taxon_name)

        # 2. For marine species, try WoRMS
        if not result and any(marine_indicator in taxon_name.lower()
                             for marine_indicator in ["shark", "ray", "fish", "coral"]):
            result = WoRMSSearcher.search(taxon_name)

        # 3. For older references, try BHL
        if not result and int(year) < 1950:
            result = BHLSearcher.search(author_name, year, self.bhl_api_key)

        # cache successful result
        if result and self.cache:
            self.cache.set(cache_key, {
                "title": result.title,
                "authors": result.authors,
                "year": result.year,
                "journal": result.journal,
                "volume": result.volume,
                "pages": result.pages,
                "doi": result.doi,
                "url": result.url,
                "source": result.source,
                "confidence": result.confidence
            })

        return result


def format_reference_citation(ref: ReferenceResult) -> str:
    """
    Format a reference result as a citation string.

    Parameters
    ----------
    ref : ReferenceResult
        The reference to format.

    Returns
    -------
    str
        Formatted citation.
    """
    parts = []

    # authors
    if ref.authors:
        if len(ref.authors) > 2:
            parts.append(f"{ref.authors[0]} et al.")
        else:
            parts.append(", ".join(ref.authors))

    # year
    parts.append(f"{ref.year}.")

    # title
    parts.append(ref.title)

    # journal info
    if ref.journal:
        journal_part = ref.journal
        if ref.volume:
            journal_part += f" {ref.volume}"
        if ref.pages:
            journal_part += f":{ref.pages}"
        parts.append(journal_part)

    return " ".join(parts)