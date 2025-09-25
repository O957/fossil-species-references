"""
Query the Paleobiology Database for publication
information about fauna. This script retrieves the
original publication, author, and year for given organism
names from the Paleobiology Database (PBDB). It can
process a single species or multiple species from a text
file.
"""

import argparse
import json
import sys
from pathlib import Path
from time import sleep

import requests

PBDB_BASE_URL = "https://paleobiodb.org/data1.2"
DEFAULT_TIMEOUT = 10
NOT_AVAILABLE = "Not available"
DISPLAY_WIDTH = 80
API_DELAY = 0.1  # seconds between requests to be respectful to API
SEPARATOR = "=" * DISPLAY_WIDTH
SUBSEPARATOR = "-" * DISPLAY_WIDTH


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
    attribution: str, ref_author: str, ref_year: str
) -> bool:
    """
    Check if taxonomic attribution matches the reference.

    Parameters
    ----------
    attribution : str
        The taxonomic attribution (e.g., "Whitley 1939").
    ref_author : str
        The reference author.
    ref_year : str
        The reference year.

    Returns
    -------
    bool
        True if there's a mismatch, False otherwise.
    """
    if attribution == NOT_AVAILABLE or ref_author == NOT_AVAILABLE:
        return False

    # clean up attribution for comparison
    att_clean = attribution.replace("(", "").replace(")", "").lower()
    ref_combined = f"{ref_author} {ref_year}".lower()

    # check if they don't match
    return att_clean not in ref_combined and not ref_combined.startswith(
        att_clean.split()[0]
    )


def process_pbdb_record(record: dict, organism_name: str) -> dict:
    """
    Process a PBDB record into standardized format.

    Parameters
    ----------
    record : dict
        The PBDB record.
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

    # extract year from author attribution
    year = extract_year_from_attribution(author)

    # check if attribution matches reference
    attribution_mismatch = check_attribution_mismatch(
        author, ref_author, ref_year
    )

    return {
        "organism": record.get("nam", organism_name),
        "author": author,
        "year": year,
        "full_reference": record.get("ref", NOT_AVAILABLE),
        "attribution_mismatch": attribution_mismatch,
        "ref_author": ref_author,
        "ref_year": ref_year,
    }


def query_pbdb(organism_name: str) -> dict | None:
    """
    Retrieve publication information for a given organism
    from PBDB.

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
            return None

        record = data["records"][0]
        return process_pbdb_record(record, organism_name)

    except requests.RequestException as e:
        return {"error": f"Connection error: {e}", "organism": organism_name}
    except json.JSONDecodeError as e:
        return {"error": f"Parse error: {e}", "organism": organism_name}


def query_multiple_species(
    species_list: list[str],
    delay: float = API_DELAY,
    show_progress: bool = False,
) -> tuple[list[dict], list[str], list[dict]]:
    """
    Query PBDB for multiple species with rate limiting.

    Parameters
    ----------
    species_list : list[str]
        List of scientific names to query.
    delay : float
        Seconds to wait between API requests.
    show_progress : bool
        Whether to show progress to stderr.

    Returns
    -------
    tuple[list[dict], list[str], list[dict]]
        (successful_results, not_found_species,
        error_results)
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

        if i > 0 and delay > 0:
            sleep(delay)

        info = query_pbdb(species)

        if info is None:
            not_found.append(species)
        elif "error" in info:
            errors.append(info)
        else:
            results.append(info)

    if show_progress and total > 3:
        print(" " * 80, file=sys.stderr, end="\r")  # clear progress line

    return results, not_found, errors


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
        f"\nOrganism: {info['organism']}",
        f"Taxonomic Authority: {info['author']}",
    ]

    if info["year"]:
        lines.append(f"Year: {info['year']}")

    if info.get("attribution_mismatch"):
        lines.append(
            f"\n⚠️  WARNING: The taxonomic authority ({info['author']}) does "
            "not match"
        )
        lines.append(
            f"   the reference below ({info.get('ref_author', 'N/A')} "
            f"{info.get('ref_year', 'N/A')})"
        )
        lines.append(
            f"   The original paper by {info['author']} may not be in PBDB."
        )

    lines.extend(["\nReference in PBDB:", info["full_reference"]])

    return "\n".join(lines)


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
        f"\nNo publication information found for '{organism}' in the "
        "Paleobiology Database.\n"
        "\nPossible reasons:\n"
        "  - The species name may be spelled differently\n"
        "  - The species may not be in the database\n"
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
    output.append(f"\n{SEPARATOR}")
    output.append("PUBLICATION LOOKUP RESULTS")
    output.append(SEPARATOR)
    output.append(f"Total species queried: {total}")
    output.append(f"Found: {len(results)}")
    output.append(f"Not found: {len(not_found)}")
    if errors:
        output.append(f"Errors: {len(errors)}")
    output.append(SEPARATOR)

    # successful results
    for info in results:
        output.append(format_single_result(info))
        output.append(SUBSEPARATOR)

    # not found species
    if not_found:
        output.append(f"\n{SEPARATOR}")
        output.append("SPECIES NOT FOUND IN PBDB:")
        output.append(SEPARATOR)
        for species in not_found:
            output.append(f"  - {species}")

    # errors
    if errors:
        output.append(f"\n{SEPARATOR}")
        output.append("QUERY ERRORS:")
        output.append(SEPARATOR)
        for error_info in errors:
            output.append(
                f"  - {error_info['organism']}: {error_info['error']}"
            )

    return "\n".join(output)


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


def main():
    """
    Main function to handle command line arguments and execute queries.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Look up publication information for species in the Paleobiology "
            "Database"
        ),
        epilog="Examples:\n"
        "  %(prog)s 'Enchodus petrosus'      # Single species\n"
        "  %(prog)s -f species.txt           # Multiple species from file\n"
        "  %(prog)s -f species.txt -j        # Output as JSON\n"
        "  %(prog)s -f species.txt --no-delay # No rate limiting",
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

    # api options
    parser.add_argument(
        "--no-delay",
        action="store_true",
        help="Disable rate limiting between API requests",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress when querying multiple species",
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
        delay = 0 if args.no_delay else API_DELAY
        results, not_found, errors = query_multiple_species(
            species_list, delay=delay, show_progress=args.progress
        )

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
        info = query_pbdb(args.organism)

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
