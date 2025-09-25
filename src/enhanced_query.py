"""
Enhanced PBDB query with fallback reference resolution.
This demonstrates how to integrate the reference resolver
with the existing PBDB lookup functionality.
"""

import json

import requests

from reference_resolver import (
    ReferenceResolver,
    format_reference_citation,
)

PBDB_BASE_URL = "https://paleobiodb.org/data1.2"
DEFAULT_TIMEOUT = 10
NOT_AVAILABLE = "Not available"


def enhanced_query_pbdb(
    organism_name: str, resolve_missing: bool = True, bhl_api_key: str = None
) -> dict:
    """
    Enhanced PBDB query with fallback reference resolution.

    Parameters
    ----------
    organism_name : str
        Scientific name of the organism.
    resolve_missing : bool
        Whether to attempt resolving missing original references.
    bhl_api_key : str
        Optional BHL API key for better results.

    Returns
    -------
    Dict
        Enhanced result dictionary.
    """
    # first, do the standard PBDB query
    params = {"name": organism_name, "show": "attr,ref,refattr,app"}

    try:
        response = requests.get(
            f"{PBDB_BASE_URL}/taxa/list.json",
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("records"):
            return {"error": "No records found", "organism": organism_name}

        record = data["records"][0]

        # process the PBDB record as before
        from streamlit_app import process_pbdb_record

        result = process_pbdb_record(record, organism_name)

        # if there's an attribution mismatch and resolution is enabled
        if resolve_missing and result.get("attribution_mismatch"):
            resolver = ReferenceResolver(
                use_cache=True, bhl_api_key=bhl_api_key
            )

            original_ref = resolver.resolve(
                taxon_name=organism_name,
                authority=result["author"],
                year=result["year"],
            )

            if original_ref:
                result["original_reference"] = {
                    "title": original_ref.title,
                    "authors": original_ref.authors,
                    "year": original_ref.year,
                    "journal": original_ref.journal,
                    "volume": original_ref.volume,
                    "pages": original_ref.pages,
                    "doi": original_ref.doi,
                    "url": original_ref.url,
                    "source": original_ref.source,
                    "confidence": original_ref.confidence,
                    "formatted_citation": format_reference_citation(
                        original_ref
                    ),
                }
            else:
                result["original_reference"] = None
                result["resolution_attempted"] = True

        return result

    except requests.RequestException as e:
        return {"error": f"Connection error: {e}", "organism": organism_name}
    except json.JSONDecodeError as e:
        return {"error": f"Parse error: {e}", "organism": organism_name}


def display_enhanced_result(result: dict) -> str:
    """
    Format enhanced result for display.

    Parameters
    ----------
    result : Dict
        Enhanced query result.

    Returns
    -------
    str
        Formatted display string.
    """
    if "error" in result:
        return f"Error: {result['error']}"

    lines = [
        f"Organism: {result['organism']}",
        f"Taxonomic Authority: {result['author']}",
    ]

    if result.get("year"):
        lines.append(f"Year: {result['year']}")

    # show PBDB reference
    lines.extend(["", "Reference in PBDB:", result["full_reference"]])

    # if there was a mismatch, show resolution results
    if result.get("attribution_mismatch"):
        lines.extend(
            [
                "",
                "⚠️ Attribution Mismatch Detected:",
                f"   Taxonomic Authority: {result['author']}",
                f"   PBDB Reference: {result.get('ref_author', 'N/A')} {result.get('ref_year', 'N/A')}",
            ]
        )

        if result.get("original_reference"):
            orig = result["original_reference"]
            lines.extend(
                [
                    "",
                    f"✅ Original Reference Found (via {orig['source']}):",
                    f"   {orig['formatted_citation']}",
                ]
            )

            if orig.get("doi"):
                lines.append(f"   DOI: {orig['doi']}")
            if orig.get("url"):
                lines.append(f"   URL: {orig['url']}")

            lines.append(f"   Confidence: {orig['confidence']:.1%}")

        elif result.get("resolution_attempted"):
            lines.extend(
                [
                    "",
                    "❌ Could not locate original reference in external sources",
                    "   The original paper may not be digitized or indexed",
                ]
            )

    return "\n".join(lines)


# example usage and testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        organism = sys.argv[1]

        print(f"Enhanced query for: {organism}")
        print("=" * 50)

        # test with resolution enabled
        result = enhanced_query_pbdb(organism, resolve_missing=True)
        print(display_enhanced_result(result))

        print("\n" + "=" * 50)
        print("Raw result data:")
        print(json.dumps(result, indent=2))
    else:
        # run test examples
        test_species = [
            "Squalicorax",  # known mismatch case
            "Tyrannosaurus rex",  # should match
            "Enchodus petrosus",  # should match
        ]

        for species in test_species:
            print(f"\nTesting: {species}")
            print("-" * 30)
            result = enhanced_query_pbdb(species)
            print(display_enhanced_result(result))
            print()
