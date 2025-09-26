"""
Enhanced PBDB query with fallback reference resolution using functions.
This demonstrates how to integrate the reference resolver functions
with the existing PBDB lookup functionality.
"""

import json
import sys
import time

import requests

from config_loader import (
    NOT_AVAILABLE,
)
from local_data_query import query_pbdb_local
from pbdb_publication_lookup import (
    normalize_taxonomic_authority,
    process_pbdb_record,
)
from reference_resolver_functions import (
    format_reference_citation,
    resolve_reference,
    resolve_reference_by_title,
    validate_reference_match,
)


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
    # use local data instead of API
    record = query_pbdb_local(organism_name)

    if record is None:
        return {"error": "No records found", "organism": organism_name}

    if "error" in record:
        return record

    # process the PBDB record as before
    result = process_pbdb_record(record, organism_name)

    # always attempt to find external links when resolution is enabled
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
            # no mismatch: search for the specific PBDB paper by title
            original_ref = resolve_reference_by_title(
                pbdb_reference=result["full_reference"],
                authority=result["author"],
                year=result["year"],
                use_cache=True,
            )

        if original_ref:
            # when searching by title (no mismatch), we expect a match
            # when searching by author/taxon (mismatch), validate normally
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
                # external reference doesn't match PBDB reference, don't show it
                result["external_reference"] = None
                result["resolution_attempted"] = True
                result["validation_failed"] = True
        else:
            result["external_reference"] = None
            result["resolution_attempted"] = True

    return result


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
        f"Taxonomic Authority: {normalize_taxonomic_authority(result['author'])}",
    ]

    if result.get("year"):
        lines.append(f"Year: {result['year']}")

    # show PBDB reference
    lines.extend(["", "Reference in PBDB:", result["full_reference"]])

    # show external reference if found
    if result.get("external_reference"):
        ext = result["external_reference"]
        lines.extend(
            [
                "",
                f"🔗 External Reference Found (via {ext['source']}):",
                f"   {ext['formatted_citation']}",
            ]
        )

        if ext.get("doi"):
            lines.append(f"   DOI: {ext['doi']}")
        if ext.get("url"):
            lines.append(f"   URL: {ext['url']}")

    # if there was a mismatch, show additional context
    if result.get("attribution_mismatch"):
        lines.extend(
            [
                "",
                "⚠️ Attribution Mismatch Detected:",
                f"   Taxonomic Authority: {result['author']}",
                f"   PBDB Reference: {result.get('ref_author', 'N/A')} {result.get('ref_year', 'N/A')}",
            ]
        )

        if result.get("external_reference"):
            lines.append(
                "   The external reference above is likely the original describing paper."
            )
        elif result.get("validation_failed"):
            lines.extend(
                [
                    "",
                    "ℹ️  External reference found but did not match PBDB reference",
                    "   Hiding potentially unrelated paper to avoid confusion",
                ]
            )
        elif result.get("resolution_attempted"):
            lines.extend(
                [
                    "",
                    "❌ Could not locate original reference in external sources",
                    "   The original paper may not be digitized or indexed",
                ]
            )

    return "\n".join(lines)


def query_multiple_species_enhanced(
    species_list: list[str],
    resolve_missing: bool = True,
    bhl_api_key: str = None,
    show_progress: bool = False,
) -> tuple[list[dict], list[str], list[dict]]:
    """
    Query PBDB for multiple species with enhanced resolution.

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
                file=sys.stderr,
                end="\r",
            )

        # rate limiting
        if i > 0:
            time.sleep(0.5)

        info = enhanced_query_pbdb(
            species.strip(), resolve_missing, bhl_api_key
        )

        if info is None:
            not_found.append(species)
        elif "error" in info:
            errors.append(info)
        else:
            results.append(info)

    if show_progress and total > 3:
        print(" " * 80, file=sys.stderr, end="\r")  # clear progress line

    return results, not_found, errors


# example usage and testing
if __name__ == "__main__":
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
