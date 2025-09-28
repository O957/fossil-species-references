"""
Enhanced query with ZooBank and external reference resolution.
This demonstrates integration of ZooBank lookup with external reference search.
"""

import json
import time

from config_loader import (
    NOT_AVAILABLE,
)
from zoobank_query import query_species_info
from publication_lookup import (
    normalize_taxonomic_authority,
    process_species_record,
)
from reference_resolver_functions import (
    format_reference_citation,
    resolve_reference,
    resolve_reference_by_title,
    validate_reference_match,
)


def enhanced_query_species(
    organism_name: str, resolve_missing: bool = True, bhl_api_key: str = None
) -> dict:
    """
    Enhanced species query with fallback reference resolution.

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
    dict
        Enhanced result dictionary.
    """
    # use ZooBank with PBDB fallback
    record = query_species_info(organism_name)

    if record is None:
        return {"error": "No records found", "organism": organism_name}

    if "error" in record:
        return record

    # process the record as before
    result = process_species_record(record, organism_name)

    # attempt to find external links when resolution is enabled
    if resolve_missing:
        # choose search strategy based on whether there's a mismatch
        if result.get("attribution_mismatch"):
            # mismatch: search by author/year/taxon to find original paper
            original_ref = resolve_reference(
                taxon_name=organism_name,
                authority=result["author"],
                year=result["year"],
                bhl_api_key=bhl_api_key,
                use_cache=True,
            )
        else:
            # no mismatch: check if we have DOI from ZooBank/PBDB, otherwise search by title
            if result.get("doi") and result["doi"] != NOT_AVAILABLE:
                # we have DOI from database - use it directly
                result["external_reference"] = {
                    "title": "", # title would need parsing from full reference
                    "authors": [record.get("aut", "")],
                    "year": record.get("pby", ""),
                    "journal": "",  # would need parsing from full reference
                    "volume": None,
                    "pages": None,
                    "doi": result["doi"],
                    "url": f"https://doi.org/{result['doi']}",
                    "source": result["source"],
                }
                result["external_reference"]["formatted_citation"] = format_reference_citation(
                    result["external_reference"]
                )
                return result
            else:
                # no DOI: search for the specific paper by title to get DOI/URL
                original_ref = resolve_reference_by_title(
                    pbdb_reference=result["full_reference"],
                    authority=result["author"],
                    year=result["year"],
                    use_cache=True,
                )

        if original_ref:
            # external search found a reference
            if result.get("attribution_mismatch"):
                is_valid_match = validate_reference_match(
                    pbdb_reference=result["full_reference"],
                    external_reference=original_ref,
                    attribution_mismatch=True,  # always show for mismatches
                )
            else:
                # title-based search, assume valid (we searched for this specific paper)
                is_valid_match = True

            if is_valid_match:
                result["external_reference"] = original_ref
                result["external_reference"]["formatted_citation"] = (
                    format_reference_citation(original_ref)
                )

                # if there's a mismatch, mark it as the original reference too
                if result.get("attribution_mismatch"):
                    result["original_reference"] = result[
                        "external_reference"
                    ]
            else:
                # external reference doesn't match database reference, don't show it
                result["external_reference"] = None
                result["resolution_attempted"] = True
                result["validation_failed"] = True
        else:
            result["external_reference"] = None
            result["resolution_attempted"] = True

    return result


def query_multiple_species_enhanced(
    species_list: list[str],
    resolve_missing: bool = True,
    bhl_api_key: str = None,
    show_progress: bool = False,
) -> tuple[list[dict], list[str], list[dict]]:
    """
    Query multiple species with enhanced resolution.

    Parameters
    ----------
    species_list : list[str]
        List of species names to query.
    resolve_missing : bool
        Whether to resolve missing references.
    bhl_api_key : str
        Optional BHL API key.
    show_progress : bool
        Whether to show progress.

    Returns
    -------
    tuple[list[dict], list[str], list[dict]]
        (successful_results, not_found_species, error_results)
    """
    results = []
    not_found = []
    errors = []

    total = len(species_list)
    for i, species in enumerate(species_list):
        if show_progress and total > 3:
            print(
                f"Querying {i + 1}/{total}: {species}...",
                end="\\r",
            )

        # rate limiting
        if i > 0:
            time.sleep(0.3)

        info = enhanced_query_species(
            species.strip(), resolve_missing, bhl_api_key
        )

        if info is None:
            not_found.append(species)
        elif "error" in info:
            errors.append(info)
        else:
            results.append(info)

    if show_progress and total > 3:
        print(" " * 80, end="\\r")  # clear progress line

    return results, not_found, errors


def display_enhanced_result(result: dict) -> str:
    """
    Format enhanced result for display.

    Parameters
    ----------
    result : dict
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

    lines.append(f"Source: {result.get('source', 'Unknown')}")

    # show database reference
    lines.extend(["", "Reference:", result["full_reference"]])

    # show DOI/ZooBank info if available
    if result.get("doi") and result["doi"] != NOT_AVAILABLE:
        lines.append(f"DOI: {result['doi']}")

    if result.get("zoobank_id") and result["zoobank_id"] != NOT_AVAILABLE:
        lines.append(f"ZooBank ID: {result['zoobank_id']}")

    # if there was a mismatch, show resolution results
    if result.get("attribution_mismatch"):
        lines.extend(
            [
                "",
                "⚠️ Attribution Mismatch Detected:",
                f"   Taxonomic Authority: {result['author']}",
                f"   Database Reference: {result.get('ref_author', 'N/A')} {result.get('ref_year', 'N/A')}",
            ]
        )

        if result.get("external_reference"):
            orig = result["external_reference"]
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

            if orig.get("relevance_score"):
                lines.append(f"   Relevance Score: {orig['relevance_score']}")

        elif result.get("resolution_attempted"):
            lines.extend(
                [
                    "",
                    "❌ Could not locate original reference in external sources",
                    "   The original paper may not be digitized or indexed",
                ]
            )
    elif result.get("external_reference"):
        # no mismatch but found external reference with DOI/URL
        ext = result["external_reference"]
        lines.extend(
            [
                "",
                f"🔗 Enhanced Reference Info (via {ext['source']}):",
            ]
        )

        if ext.get("doi"):
            lines.append(f"   DOI: {ext['doi']}")
        if ext.get("url"):
            lines.append(f"   URL: {ext['url']}")

    return "\\n".join(lines)


# example usage and testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        organism = sys.argv[1]

        print(f"Enhanced query for: {organism}")
        print("=" * 50)

        # test with resolution enabled
        result = enhanced_query_species(organism, resolve_missing=True)
        print(display_enhanced_result(result))

        print("\\n" + "=" * 50)
        print("Raw result data:")
        print(json.dumps(result, indent=2, default=str))
    else:
        # run test examples
        test_species = [
            "Squalicorax",  # known mismatch case
            "Tyrannosaurus rex",  # should match
            "Enchodus petrosus",  # should match
        ]

        for species in test_species:
            print(f"\\nTesting: {species}")
            print("-" * 30)
            result = enhanced_query_species(species)
            print(display_enhanced_result(result))
            print()