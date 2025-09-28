"""
Example integration with GBIF Backbone Taxonomy for finding original descriptions.
GBIF actually tracks nomenclatural acts and original publications.
"""

import requests
import json
from typing import Optional, Dict


def query_gbif_species(species_name: str) -> Optional[Dict]:
    """
    Query GBIF Backbone Taxonomy for species information including original publication.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.

    Returns
    -------
    Optional[Dict]
        Species information including original publication, or None if not found.
    """
    # GBIF Species Match API
    base_url = "https://api.gbif.org/v1"

    # First, match the species name to get the usage key
    match_url = f"{base_url}/species/match"
    params = {
        "name": species_name,
        "strict": False
    }

    try:
        response = requests.get(match_url, params=params, timeout=5)
        response.raise_for_status()
        match_data = response.json()

        if match_data.get("matchType") == "NONE":
            return None

        usage_key = match_data.get("usageKey")
        if not usage_key:
            return None

        # Get detailed species information including publications
        species_url = f"{base_url}/species/{usage_key}"
        species_response = requests.get(species_url, timeout=5)
        species_response.raise_for_status()
        species_data = species_response.json()

        # Extract relevant information
        result = {
            "scientificName": species_data.get("scientificName"),
            "authorship": species_data.get("authorship"),
            "publishedIn": species_data.get("publishedIn"),  # Original publication!
            "accordingTo": species_data.get("accordingTo"),
            "nomenclaturalStatus": species_data.get("nomenclaturalStatus"),
            "taxonomicStatus": species_data.get("taxonomicStatus"),
            "year": species_data.get("year"),
            "source": "GBIF Backbone Taxonomy",
            "gbif_key": usage_key
        }

        # Get references if available
        references_url = f"{base_url}/species/{usage_key}/references"
        try:
            ref_response = requests.get(references_url, timeout=5)
            ref_response.raise_for_status()
            references = ref_response.json().get("results", [])
            if references:
                result["references"] = references[:5]  # First 5 references
        except:
            pass

        return result

    except Exception as e:
        print(f"GBIF query error: {e}")
        return None


def query_plazi_treatments(species_name: str) -> Optional[Dict]:
    """
    Query Plazi TreatmentBank for taxonomic treatments and original descriptions.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.

    Returns
    -------
    Optional[Dict]
        Treatment information including citations, or None if not found.
    """
    # Plazi SPARQL endpoint for TreatmentBank
    sparql_endpoint = "http://treatment.plazi.org/sparql"

    # SPARQL query to find treatments for a taxon
    query = f"""
    PREFIX trt: <http://plazi.org/vocab/treatment#>
    PREFIX dwc: <http://rs.tdwg.org/dwc/terms/>

    SELECT ?treatment ?scientificName ?author ?year ?publication ?doi
    WHERE {{
      ?treatment a trt:Treatment ;
                 trt:definesTaxonConcept ?taxon .
      ?taxon dwc:scientificName "{species_name}" ;
             dwc:scientificNameAuthorship ?author .
      OPTIONAL {{ ?treatment trt:publishedIn ?publication }}
      OPTIONAL {{ ?treatment trt:year ?year }}
      OPTIONAL {{ ?treatment trt:doi ?doi }}
    }}
    LIMIT 5
    """

    try:
        response = requests.get(
            sparql_endpoint,
            params={"query": query, "format": "json"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for binding in data.get("results", {}).get("bindings", []):
            results.append({
                "treatment_uri": binding.get("treatment", {}).get("value"),
                "author": binding.get("author", {}).get("value"),
                "year": binding.get("year", {}).get("value"),
                "publication": binding.get("publication", {}).get("value"),
                "doi": binding.get("doi", {}).get("value"),
                "source": "Plazi TreatmentBank"
            })

        return results[0] if results else None

    except Exception as e:
        print(f"Plazi query error: {e}")
        return None


def query_worms_species(species_name: str) -> Optional[Dict]:
    """
    Query WoRMS (World Register of Marine Species) for species information.
    Good for marine fossils.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.

    Returns
    -------
    Optional[Dict]
        Species information including original description, or None if not found.
    """
    base_url = "https://www.marinespecies.org/rest"

    # Search for the taxon
    search_url = f"{base_url}/AphiaRecordsByMatchNames"
    params = {
        "scientificnames[]": species_name,
        "marine_only": False  # Include fossils and non-marine
    }

    try:
        response = requests.get(search_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if not data or not data[0]:
            return None

        # Get the first match
        matches = data[0]
        if not matches:
            return None

        record = matches[0]
        aphia_id = record.get("AphiaID")

        # Get detailed record with sources
        detail_url = f"{base_url}/AphiaRecordByAphiaID/{aphia_id}"
        detail_response = requests.get(detail_url, timeout=5)
        detail_response.raise_for_status()
        detail_data = detail_response.json()

        # Get sources (original description)
        sources_url = f"{base_url}/AphiaSourcesByAphiaID/{aphia_id}"
        sources_response = requests.get(sources_url, timeout=5)
        sources_response.raise_for_status()
        sources_data = sources_response.json()

        # Find original description in sources
        original_description = None
        for source in sources_data:
            if source.get("use") == "original description":
                original_description = source
                break

        result = {
            "scientificName": detail_data.get("scientificname"),
            "authority": detail_data.get("authority"),
            "originalDescription": original_description,
            "sources": sources_data[:3],  # First 3 sources
            "isFossil": detail_data.get("isFossil"),
            "source": "WoRMS",
            "aphiaId": aphia_id
        }

        return result

    except Exception as e:
        print(f"WoRMS query error: {e}")
        return None


def integrated_nomenclature_search(species_name: str) -> Dict:
    """
    Search multiple nomenclatural databases for original descriptions.

    Parameters
    ----------
    species_name : str
        Scientific name to search for.

    Returns
    -------
    Dict
        Combined results from multiple sources.
    """
    results = {
        "species": species_name,
        "sources_checked": [],
        "original_publication": None,
        "confidence": 0
    }

    # Try GBIF first (most comprehensive)
    print(f"Checking GBIF for {species_name}...")
    gbif_result = query_gbif_species(species_name)
    if gbif_result and gbif_result.get("publishedIn"):
        results["gbif"] = gbif_result
        results["original_publication"] = gbif_result["publishedIn"]
        results["confidence"] = 0.8
        results["sources_checked"].append("GBIF")

    # Try WoRMS (good for marine species)
    print(f"Checking WoRMS for {species_name}...")
    worms_result = query_worms_species(species_name)
    if worms_result and worms_result.get("originalDescription"):
        results["worms"] = worms_result
        if not results["original_publication"]:
            results["original_publication"] = worms_result["originalDescription"].get("reference")
            results["confidence"] = 0.9  # WoRMS explicitly marks original descriptions
        results["sources_checked"].append("WoRMS")

    # Try Plazi (taxonomic treatments)
    print(f"Checking Plazi for {species_name}...")
    plazi_result = query_plazi_treatments(species_name)
    if plazi_result:
        results["plazi"] = plazi_result
        if not results["original_publication"] and plazi_result.get("publication"):
            results["original_publication"] = plazi_result["publication"]
            results["confidence"] = 0.7
        results["sources_checked"].append("Plazi")

    return results


# Example usage
if __name__ == "__main__":
    # Test with various species
    test_species = [
        "Tyrannosaurus rex",
        "Carcharodon megalodon",
        "Enchodus petrosus",
        "Homo sapiens"
    ]

    for species in test_species:
        print(f"\n{'='*60}")
        print(f"Searching for: {species}")
        print('='*60)

        result = integrated_nomenclature_search(species)

        print(f"Sources checked: {', '.join(result['sources_checked'])}")

        if result.get("original_publication"):
            print(f"Original publication found!")
            print(f"Publication: {result['original_publication']}")
            print(f"Confidence: {result['confidence']}")

        if result.get("gbif"):
            print(f"\nGBIF Data:")
            print(f"  Authority: {result['gbif'].get('authorship')}")
            print(f"  Published in: {result['gbif'].get('publishedIn')}")

        if result.get("worms"):
            print(f"\nWoRMS Data:")
            print(f"  Authority: {result['worms'].get('authority')}")
            if result['worms'].get('originalDescription'):
                print(f"  Original: {result['worms']['originalDescription'].get('reference')}")

        # Save results to JSON file
        filename = f"gbif_example_{species.replace(' ', '_')}.json"
        with open(filename, "w") as f:
            json.dump(result, f, indent=2, default=str)