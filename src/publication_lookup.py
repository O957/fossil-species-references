"""
Publication lookup using ZooBank and PBDB fallback.
This script retrieves the original publication, author, and year for given organism
names, first trying ZooBank, then falling back to PBDB dataset.
"""

import argparse
import json
import sys
from pathlib import Path
from time import sleep

from config_loader import (
    API_DELAY,
    NOT_AVAILABLE,
)
from zoobank_query import query_species_info, query_multiple_species

DISPLAY_WIDTH = 80
SEPARATOR = "=" * DISPLAY_WIDTH
SUBSEPARATOR = "-" * DISPLAY_WIDTH


def normalize_taxonomic_authority(authority: str) -> str:
    """
    Normalize taxonomic authority to always have parentheses.

    Parameters
    ----------
    authority : str
        The taxonomic authority string.

    Returns
    -------
    str
        Normalized authority with parentheses.
    """
    if authority == NOT_AVAILABLE:
        return authority

    # remove existing parentheses and normalize
    clean_authority = authority.replace("(", "").replace(")", "").strip()

    # add parentheses
    return f"({clean_authority})"


def extract_year_from_attribution(attribution: str) -> str | None:
    """
    Extract year from taxonomic attribution string.

    Parameters
    ----------
    attribution : str
        The attribution string (e.g., "Cope 1874").

    Returns
    -------
    str | None
        The extracted year or None if not found.
    """
    if attribution == NOT_AVAILABLE:
        return None

    parts = attribution.split()
    if parts and parts[-1].isdigit():
        return parts[-1]
    return None


def check_attribution_mismatch(
    attribution: str, reference: str
) -> bool:
    """
    Check if taxonomic attribution matches the reference.

    Parameters
    ----------
    attribution : str
        The taxonomic attribution (e.g., "Whitley 1939").
    reference : str
        The full reference text.

    Returns
    -------
    bool
        True if there's a mismatch, False otherwise.
    """
    if attribution == NOT_AVAILABLE or not reference:
        return False

    # clean up attribution - remove parentheses
    att_clean = attribution.replace("(", "").replace(")", "").strip()
    ref_lower = reference.lower()

    # extract author and year from attribution
    att_parts = att_clean.split()
    if not att_parts:
        return False

    # check if both author and year appear in reference
    for part in att_parts:
        if part.lower() not in ref_lower:
            return True  # mismatch if any part is missing

    return False  # no mismatch if all parts found


def process_species_record(record: dict, organism_name: str) -> dict:
    """
    Process a species record into standardized format.

    Parameters
    ----------
    record : dict
        The species record from ZooBank or PBDB.
    organism_name : str
        The original organism name queried.

    Returns
    -------
    dict
        Processed publication information.
    """
    # taxonomic attribution (original author and year)
    author = record.get("att", NOT_AVAILABLE)

    # reference author and year (may differ from attribution)
    ref_author = record.get("aut", NOT_AVAILABLE)
    ref_year = record.get("pby", NOT_AVAILABLE)
    full_reference = record.get("ref", NOT_AVAILABLE)

    # extract year from author attribution
    year = extract_year_from_attribution(author)

    # check if attribution matches reference
    attribution_mismatch = check_attribution_mismatch(author, full_reference)

    # get source and additional info
    source = record.get("source", "Unknown")
    doi = record.get("doi", NOT_AVAILABLE)
    zoobank_id = record.get("zoobank_id", NOT_AVAILABLE)

    return {
        "organism": record.get("nam", organism_name),
        "author": author,
        "year": year,
        "full_reference": full_reference,
        "attribution_mismatch": attribution_mismatch,
        "ref_author": ref_author,
        "ref_year": ref_year,
        "source": source,
        "doi": doi,
        "zoobank_id": zoobank_id,
    }


def query_publication_info(organism_name: str) -> dict | None:
    """
    Retrieve publication information for a given organism from ZooBank/PBDB.

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
    # use ZooBank with PBDB fallback
    record = query_species_info(organism_name)

    if record is None:
        return None

    if "error" in record:
        return record

    return process_species_record(record, organism_name)


def format_single_result(info: dict) -> str:
    """
    Format a single publication result for display.

    Parameters
    ----------
    info : dict
        Dictionary containing publication information.

    Returns
    -------
    str
        Formatted output string.
    """
    lines = [
        f"\\nOrganism: {info['organism']}",
        f"Taxonomic Authority: {normalize_taxonomic_authority(info['author'])}",
    ]

    if info["year"]:
        lines.append(f"Year: {info['year']}")

    lines.append(f"Source: {info.get('source', 'Unknown')}")

    # show DOI if available
    if info.get("doi") and info["doi"] != NOT_AVAILABLE:
        lines.append(f"DOI: {info['doi']}")

    # show ZooBank ID if available
    if info.get("zoobank_id") and info["zoobank_id"] != NOT_AVAILABLE:
        lines.append(f"ZooBank ID: {info['zoobank_id']}")

    if info.get("attribution_mismatch"):
        lines.append(
            f"\\n⚠️  WARNING: The taxonomic authority ({info['author']}) does "
            "not match"
        )
        lines.append(
            f"   the reference below ({info.get('ref_author', 'N/A')} "
            f"{info.get('ref_year', 'N/A')})"
        )
        lines.append(
            f"   The original paper by {info['author']} may not be in the database."
        )

    lines.extend(["\\nReference:", info["full_reference"]])

    return "\\n".join(lines)


def format_not_found_message(organism: str) -> str:
    """
    Format standard 'not found' error message.

    Parameters
    ----------
    organism : str
        Name of the organism that wasn't found.

    Returns
    -------
    str
        Formatted error message.
    """
    return (
        f"\\nNo publication information found for '{organism}' in "
        "ZooBank or PBDB dataset.\\n"
        "\\nPossible reasons:\\n"
        "  - The species name may be spelled differently\\n"
        "  - The species may not be in the databases\\n"
        "  - Try searching without 'cf.' or other qualifiers"
    )


def format_multiple_results(
    results: list[dict], not_found: list[str], errors: list[dict], total: int
) -> str:
    """
    Format multiple query results for display.

    Parameters
    ----------
    results : list[dict]
        Successful query results.
    not_found : list[str]
        Species names that weren't found.
    errors : list[dict]
        Query errors.
    total : int
        Total number of queries attempted.

    Returns
    -------
    str
        Formatted output string.
    """
    output = []

    # header
    output.append(f"\\n{SEPARATOR}")
    output.append("PUBLICATION LOOKUP RESULTS")
    output.append(SEPARATOR)
    output.append(f"Total species queried: {total}")
    output.append(f"Found: {len(results)}")
    output.append(f"Not found: {len(not_found)}")
    if errors:
        output.append(f"Errors: {len(errors)}")
    output.append(SEPARATOR)

    # show source breakdown
    source_counts = {}
    for result in results:
        source = result.get("source", "Unknown")
        source_counts[source] = source_counts.get(source, 0) + 1

    if source_counts:
        output.append("Sources:")
        for source, count in source_counts.items():
            output.append(f"  - {source}: {count}")
        output.append(SUBSEPARATOR)

    # successful results
    for info in results:
        output.append(format_single_result(info))
        output.append(SUBSEPARATOR)

    # not found species
    if not_found:
        output.append(f"\\n{SEPARATOR}")
        output.append("SPECIES NOT FOUND:")
        output.append(SEPARATOR)
        for species in not_found:
            output.append(f"  - {species}")

    # errors
    if errors:
        output.append(f"\\n{SEPARATOR}")
        output.append("QUERY ERRORS:")
        output.append(SEPARATOR)
        for error_info in errors:
            output.append(
                f"  - {error_info['organism']}: {error_info['error']}"
            )

    return "\\n".join(output)


def format_json_output(
    results: list[dict], not_found: list[str], errors: list[dict]
) -> dict:
    """
    Format results as JSON structure.

    Parameters
    ----------
    results : list[dict]
        Successful query results.
    not_found : list[str]
        Species names that weren't found.
    errors : list[dict]
        Query errors.

    Returns
    -------
    dict
        Structured data ready for JSON serialization.
    """
    return {
        "found": results,
        "not_found": not_found,
        "errors": errors,
        "summary": {
            "total_queried": len(results) + len(not_found) + len(errors),
            "found_count": len(results),
            "not_found_count": len(not_found),
            "error_count": len(errors),
        },
    }


def load_species_from_file(filepath: str) -> list[str]:
    """
    Load species names from a text file (one per line).

    Parameters
    ----------
    filepath : str
        Path to the text file containing species names.

    Returns
    -------
    list[str]
        List of species names.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File '{filepath}' not found")

    species = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            # skip empty lines and comments
            if line and not line.startswith("#"):
                species.append(line)

    return species


def main():
    """
    Main function to handle command line arguments and execute queries.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Look up publication information for species using ZooBank "
            "with PBDB fallback"
        ),
        epilog="Examples:\\n"
        "  %(prog)s 'Enchodus petrosus'      # Single species\\n"
        "  %(prog)s -f species.txt           # Multiple species from file\\n"
        "  %(prog)s -f species.txt -j        # Output as JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # input arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "organism",
        nargs="?",
        help=(
            "Scientific name of a single organism (e.g., 'Enchodus petrosus')"
        ),
    )
    group.add_argument(
        "-f",
        "--file",
        help="Path to text file containing species names (one per line)",
    )

    # output options
    parser.add_argument(
        "-j", "--json", action="store_true", help="Output in JSON format"
    )

    args = parser.parse_args()

    # determine what to query
    if args.file:
        try:
            species_list = load_species_from_file(args.file)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not species_list:
            print(
                "Error: No valid species names found in file", file=sys.stderr
            )
            sys.exit(1)

        # query multiple species
        results, not_found, errors = query_multiple_species(species_list)

        # output results
        if args.json:
            output = format_json_output(results, not_found, errors)
            print(json.dumps(output, indent=2))
        else:
            output = format_multiple_results(
                results, not_found, errors, len(species_list)
            )
            print(output)

        # exit with error code if nothing was found
        if not results:
            sys.exit(1)

    else:
        # single species query
        info = query_publication_info(args.organism)

        if info is None:
            print(format_not_found_message(args.organism))
            sys.exit(1)
        elif "error" in info:
            print(
                f"Error querying '{args.organism}': {info['error']}",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            if args.json:
                print(json.dumps(info, indent=2))
            else:
                print(format_single_result(info))


if __name__ == "__main__":
    main()