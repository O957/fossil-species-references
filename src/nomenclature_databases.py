"""
Nomenclatural database integrations for finding original taxonomic descriptions.
These databases track the origin of taxonomic names, not just occurrences.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

from config_loader import CACHE_DIR_NAME, CACHE_FILE_NAME, CACHE_SUBDIR_NAME
from env_loader import get_bhl_api_key
from zoobank_query import query_pbdb_fallback
from reference_resolver_functions import resolve_reference_by_title, resolve_reference


class NomenclatureCache:
    """Cache for nomenclatural database queries."""

    def __init__(self):
        """Initialize the cache."""
        self.cache_dir = Path.home() / CACHE_DIR_NAME / CACHE_SUBDIR_NAME
        self.cache_file = self.cache_dir / "nomenclature_cache.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, indent=2, default=str)

    def get(self, key: str) -> Optional[dict]:
        """Get cached result."""
        return self.cache.get(key)

    def set(self, key: str, value: dict):
        """Set cached result."""
        self.cache[key] = value
        self._save_cache()


# Global cache instance
_cache = NomenclatureCache()


def query_gbif_backbone(species_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Query GBIF Backbone Taxonomy for species nomenclatural information.

    GBIF tracks original publications for taxonomic names.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.
    use_cache : bool
        Whether to use cached results.

    Returns
    -------
    Optional[Dict]
        Nomenclatural information including original publication.
    """
    cache_key = f"gbif:{species_name}"

    if use_cache:
        cached = _cache.get(cache_key)
        if cached:
            return cached

    base_url = "https://api.gbif.org/v1"

    try:
        # Match species name
        match_url = f"{base_url}/species/match"
        params = {"name": species_name, "strict": False}

        response = requests.get(match_url, params=params, timeout=5)
        response.raise_for_status()
        match_data = response.json()

        if match_data.get("matchType") == "NONE":
            return None

        usage_key = match_data.get("usageKey")
        if not usage_key:
            return None

        # Get detailed species information
        species_url = f"{base_url}/species/{usage_key}"
        species_response = requests.get(species_url, timeout=5)
        species_response.raise_for_status()
        species_data = species_response.json()

        # Extract nomenclatural information
        result = {
            "scientificName": species_data.get("scientificName"),
            "authorship": species_data.get("authorship"),
            "publishedIn": species_data.get("publishedIn"),  # Original publication!
            "year": extract_year_from_authority(species_data.get("authorship", "")),
            "nomenclaturalStatus": species_data.get("nomenclaturalStatus", []),
            "taxonomicStatus": species_data.get("taxonomicStatus"),
            "source": "GBIF Backbone",
            "confidence": 0.9 if species_data.get("publishedIn") else 0.7
        }

        # Cache successful result
        if use_cache:
            _cache.set(cache_key, result)

        return result

    except Exception as e:
        print(f"GBIF query error for {species_name}: {e}")
        return None


def query_worms_marine(species_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Query WoRMS (World Register of Marine Species) for nomenclatural information.

    Excellent for marine species including marine fossils.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.
    use_cache : bool
        Whether to use cached results.

    Returns
    -------
    Optional[Dict]
        Nomenclatural information including original description.
    """
    cache_key = f"worms:{species_name}"

    if use_cache:
        cached = _cache.get(cache_key)
        if cached:
            return cached

    base_url = "https://www.marinespecies.org/rest"

    try:
        # Search for the taxon
        search_url = f"{base_url}/AphiaRecordsByMatchNames"
        params = {"scientificnames[]": species_name, "marine_only": False}

        response = requests.get(search_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if not data or not data[0]:
            return None

        matches = data[0]
        if not matches:
            return None

        record = matches[0]
        aphia_id = record.get("AphiaID")

        # Get sources for original description
        sources_url = f"{base_url}/AphiaSourcesByAphiaID/{aphia_id}"
        sources_response = requests.get(sources_url, timeout=5)
        sources_response.raise_for_status()
        sources_data = sources_response.json()

        # Find original description
        original_desc = None
        for source in sources_data:
            if "original" in source.get("use", "").lower():
                original_desc = source.get("reference")
                break

        result = {
            "scientificName": record.get("scientificname"),
            "authorship": record.get("authority"),
            "publishedIn": original_desc,
            "year": extract_year_from_authority(record.get("authority", "")),
            "isFossil": record.get("isFossil"),
            "source": "WoRMS",
            "confidence": 0.95 if original_desc else 0.6
        }

        # Cache successful result
        if use_cache:
            _cache.set(cache_key, result)

        return result

    except Exception as e:
        print(f"WoRMS query error for {species_name}: {e}")
        return None


def query_itis_taxonomy(species_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Query ITIS (Integrated Taxonomic Information System) for nomenclatural information.

    US government taxonomic database.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.
    use_cache : bool
        Whether to use cached results.

    Returns
    -------
    Optional[Dict]
        Nomenclatural information.
    """
    cache_key = f"itis:{species_name}"

    if use_cache:
        cached = _cache.get(cache_key)
        if cached:
            return cached

    base_url = "https://www.itis.gov/ITISWebService/jsonservice"

    try:
        # Search by scientific name
        search_url = f"{base_url}/searchByScientificName"
        params = {"srchKey": species_name}

        response = requests.get(search_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if not data.get("scientificNames"):
            return None

        # Get first match
        match = data["scientificNames"][0]
        tsn = match.get("tsn")

        if not tsn:
            return None

        # Get publication info
        pub_url = f"{base_url}/getPublicationsFromTSN"
        pub_params = {"tsn": tsn}

        pub_response = requests.get(pub_url, params=pub_params, timeout=5)
        pub_response.raise_for_status()
        pub_data = pub_response.json()

        # Extract first publication as likely original
        original_pub = None
        if pub_data.get("publications"):
            original_pub = pub_data["publications"][0].get("pubComment")

        result = {
            "scientificName": match.get("combinedName"),
            "authorship": match.get("author"),
            "publishedIn": original_pub,
            "year": extract_year_from_authority(match.get("author", "")),
            "source": "ITIS",
            "confidence": 0.7 if original_pub else 0.5
        }

        # Cache successful result
        if use_cache:
            _cache.set(cache_key, result)

        return result

    except Exception as e:
        print(f"ITIS query error for {species_name}: {e}")
        return None


def query_bhl_taxonomic(species_name: str, author: str = None, year: str = None,
                        bhl_api_key: str = None, use_cache: bool = True) -> Optional[Dict]:
    """
    Query BHL (Biodiversity Heritage Library) for taxonomic literature.

    Essential for old paleontological literature (1800s-early 1900s).

    Parameters
    ----------
    species_name : str
        Scientific name to search for.
    author : str
        Author name to filter results.
    year : str
        Publication year to filter results.
    bhl_api_key : str
        Optional BHL API key for better rate limits.
    use_cache : bool
        Whether to use cached results.

    Returns
    -------
    Optional[Dict]
        Publication information from BHL.
    """
    cache_key = f"bhl:{species_name}:{author}:{year}"

    if use_cache:
        cached = _cache.get(cache_key)
        if cached:
            return cached

    base_url = "https://www.biodiversitylibrary.org/api3"

    try:
        # Search for taxonomic name
        params = {
            "op": "NameSearch",
            "name": species_name,
            "format": "json"
        }

        if bhl_api_key:
            params["apikey"] = bhl_api_key

        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("Status") != "ok" or not data.get("Result"):
            return None

        # Filter results by author/year if provided
        best_match = None
        for result in data["Result"]:
            title = result.get("Title", "")

            # Score based on matching author and year
            score = 0
            if author and author.lower() in title.lower():
                score += 2
            if year and year in title:
                score += 2

            # Look for "new species" or "nov." indicating original description
            if any(term in title.lower() for term in ["new species", "nov.", "n. sp.", "described"]):
                score += 3

            if not best_match or score > best_match[1]:
                best_match = (result, score)

        if not best_match:
            return None

        result_data = best_match[0]

        result = {
            "scientificName": species_name,
            "authorship": author,
            "publishedIn": result_data.get("Title"),
            "year": year or extract_year_from_title(result_data.get("Title", "")),
            "bhl_url": f"https://biodiversitylibrary.org/page/{result_data.get('PageID')}",
            "source": "BHL",
            "confidence": min(0.6 + (best_match[1] * 0.1), 0.9)
        }

        # Cache successful result
        if use_cache:
            _cache.set(cache_key, result)

        return result

    except Exception as e:
        print(f"BHL query error for {species_name}: {e}")
        return None


def query_plazi_treatments(species_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Query Plazi TreatmentBank for taxonomic treatments.

    Extracts taxonomic treatments from scientific literature.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.
    use_cache : bool
        Whether to use cached results.

    Returns
    -------
    Optional[Dict]
        Treatment information including citations.
    """
    cache_key = f"plazi:{species_name}"

    if use_cache:
        cached = _cache.get(cache_key)
        if cached:
            return cached

    # Plazi API endpoint
    base_url = "https://tb.plazi.org/GgServer/search"

    try:
        params = {
            "q": species_name,
            "limit": 10,
            "format": "json"
        }

        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("records"):
            return None

        # Find best matching treatment
        best_treatment = None
        for record in data["records"]:
            # Look for original description indicators
            if any(term in record.get("title", "").lower()
                   for term in ["new species", "sp. nov.", "gen. nov.", "described"]):
                best_treatment = record
                break

        if not best_treatment:
            best_treatment = data["records"][0]

        result = {
            "scientificName": species_name,
            "authorship": best_treatment.get("authorityName"),
            "publishedIn": best_treatment.get("articleTitle"),
            "year": best_treatment.get("publicationYear"),
            "doi": best_treatment.get("articleDoi"),
            "source": "Plazi",
            "confidence": 0.8 if best_treatment.get("articleDoi") else 0.6
        }

        # Cache successful result
        if use_cache:
            _cache.set(cache_key, result)

        return result

    except Exception as e:
        print(f"Plazi query error for {species_name}: {e}")
        return None


def integrated_nomenclature_search(species_name: str, author: str = None,
                                  year: str = None, bhl_api_key: str = None) -> Dict:
    """
    Search multiple nomenclatural databases for original descriptions.

    Searches databases in order of reliability with early stopping.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.
    author : str
        Optional author name for filtering.
    year : str
        Optional year for filtering.
    bhl_api_key : str
        Optional BHL API key.

    Returns
    -------
    Dict
        Combined results from multiple sources.
    """
    results = {
        "species": species_name,
        "query_author": author,
        "query_year": year,
        "sources_checked": [],
        "original_publication": None,
        "best_match": None,
        "confidence": 0,
        "all_results": {}
    }

    # Auto-load BHL API key if not provided
    if not bhl_api_key:
        bhl_api_key = get_bhl_api_key()

    # Search order: best/most reliable sources first
    search_functions = [
        ("GBIF", lambda: query_gbif_backbone(species_name)),
        ("WoRMS", lambda: query_worms_marine(species_name)),
        ("BHL", lambda: query_bhl_taxonomic(species_name, author, year, bhl_api_key)),
        ("ITIS", lambda: query_itis_taxonomy(species_name)),
        ("Plazi", lambda: query_plazi_treatments(species_name)),
        ("PBDB", lambda: query_pbdb_fallback(species_name))  # Final fallback
    ]

    for source_name, search_func in search_functions:
        print(f"Checking {source_name} for {species_name}...")

        try:
            result = search_func()
        except Exception as e:
            print(f"{source_name} query error for {species_name}: {e}")
            continue

        if not result:
            continue

        results["sources_checked"].append(source_name)
        results["all_results"][source_name.lower()] = result

        # Check if this result has an original publication
        publication = None
        if source_name == "PBDB":
            # For PBDB, use the reference field
            publication = result.get("ref")
            if publication and publication != "Not available":
                # Create a standardized result format
                pbdb_match = {
                    "scientificName": result.get("nam", species_name),
                    "authorship": result.get("att", "Unknown"),
                    "publishedIn": publication,
                    "year": extract_year_from_authority(result.get("att", "")),
                    "source": "PBDB Dataset",
                    "confidence": 0.6  # Lower confidence since it may not be original description
                }
                result = pbdb_match  # Standardize format
        else:
            publication = result.get("publishedIn")

        if publication and publication != "Not available":
            # Check if this is better than what we have
            current_confidence = result.get("confidence", 0.5)

            if not results["original_publication"] or current_confidence > results["confidence"]:
                results["original_publication"] = publication
                results["best_match"] = result
                results["confidence"] = current_confidence

            # Early stopping for high-confidence results
            if current_confidence >= 0.9:
                print(f"✅ High-confidence result found in {source_name}, stopping search")
                break

    # If we found a publication, try to enhance it with CrossRef
    if results.get("original_publication") and results.get("best_match"):
        print("🔍 Enhancing with CrossRef search for DOI/URL...")
        enhanced_ref = enhance_with_crossref(results["best_match"], species_name)
        if enhanced_ref:
            results["enhanced_reference"] = enhanced_ref
            # Update best match with enhanced info
            if enhanced_ref.get("doi"):
                results["best_match"]["doi"] = enhanced_ref["doi"]
            if enhanced_ref.get("url"):
                results["best_match"]["url"] = enhanced_ref["url"]

    return results


def enhance_with_crossref(publication_result: Dict, species_name: str) -> Optional[Dict]:
    """
    Enhance publication result with CrossRef DOI/URL lookup.

    Parameters
    ----------
    publication_result : Dict
        Publication result from nomenclatural database.
    species_name : str
        Species name for context.

    Returns
    -------
    Optional[Dict]
        Enhanced reference with DOI/URL or None.
    """
    try:
        # Get publication details
        publication = publication_result.get("publishedIn", "")
        authorship = publication_result.get("authorship", "")
        year = publication_result.get("year", "")

        if not publication:
            return None

        # Try title-based search first (more accurate)
        enhanced_ref = resolve_reference_by_title(
            pbdb_reference=publication,
            authority=authorship,
            year=year,
            use_cache=True
        )

        if enhanced_ref and enhanced_ref.get("doi"):
            print(f"✅ CrossRef found DOI via title search")
            return enhanced_ref

        # Fallback: try author/year search if we have them
        if authorship and year:
            enhanced_ref = resolve_reference(
                taxon_name=species_name,
                authority=authorship,
                year=year,
                use_cache=True
            )

            if enhanced_ref and enhanced_ref.get("doi"):
                print(f"✅ CrossRef found DOI via author/year search")
                return enhanced_ref

        print("⚠️ CrossRef search didn't find DOI")
        return None

    except Exception as e:
        print(f"CrossRef enhancement error: {e}")
        return None


def extract_year_from_authority(authority: str) -> Optional[str]:
    """
    Extract year from taxonomic authority string.

    Parameters
    ----------
    authority : str
        Authority string like "Cope, 1874" or "(Osborn, 1905)".

    Returns
    -------
    Optional[str]
        Extracted year or None.
    """
    if not authority:
        return None

    # Look for 4-digit year
    import re
    year_match = re.search(r'\b(17\d{2}|18\d{2}|19\d{2}|20\d{2})\b', authority)
    if year_match:
        return year_match.group(1)

    return None


def extract_year_from_title(title: str) -> Optional[str]:
    """
    Extract year from publication title.

    Parameters
    ----------
    title : str
        Publication title.

    Returns
    -------
    Optional[str]
        Extracted year or None.
    """
    if not title:
        return None

    # Look for 4-digit year
    import re
    year_match = re.search(r'\b(17\d{2}|18\d{2}|19\d{2}|20\d{2})\b', title)
    if year_match:
        return year_match.group(1)

    return None


def format_nomenclature_result(result: Dict) -> str:
    """
    Format nomenclature search results for display.

    Parameters
    ----------
    result : Dict
        Results from integrated_nomenclature_search.

    Returns
    -------
    str
        Formatted string for display.
    """
    lines = [
        f"Species: {result['species']}",
        f"Sources checked: {', '.join(result['sources_checked'])}"
    ]

    if result.get("original_publication"):
        lines.append(f"\n✅ Original Publication Found:")
        lines.append(f"   {result['original_publication']}")
        lines.append(f"   Source: {result['best_match']['source']}")
        lines.append(f"   Confidence: {result['confidence']*100:.0f}%")
    else:
        lines.append("\n❌ Original publication not found in nomenclatural databases")

    # Show all sources that had data
    if len(result.get("all_results", {})) > 1:
        lines.append("\nOther sources with data:")
        for source, data in result["all_results"].items():
            if source != result.get("best_match", {}).get("source", "").lower():
                auth = data.get("authorship", "Unknown")
                lines.append(f"  • {data['source']}: {auth}")

    return "\n".join(lines)


# Test the integration
if __name__ == "__main__":
    test_species = [
        "Tyrannosaurus rex",
        "Enchodus petrosus",
        "Squalicorax",
        "Homo sapiens"
    ]

    for species in test_species:
        print("\n" + "="*60)
        result = integrated_nomenclature_search(species)
        print(format_nomenclature_result(result))