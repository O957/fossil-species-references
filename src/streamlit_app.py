"""
Streamlit web application for PBDB Publication Lookup.
This app allows users to query the Paleobiology Database
for publication information about species, either
individually or in batch from a file.
"""

import json
import time
from io import StringIO

import requests
import streamlit as st

PBDB_BASE_URL = "https://paleobiodb.org/data1.2"
DEFAULT_TIMEOUT = 10
NOT_AVAILABLE = "Not available"
API_DELAY = 0.1


def configure_page():
    """
    Configure Streamlit page settings.
    """
    st.set_page_config(
        page_title="PBDB Publication Lookup", page_icon="📚", layout="wide"
    )


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
        Dictionary containing publication info, error
        info, or None if not found.
    """
    params = {"name": organism_name, "show": "attr,ref,app"}

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
        author = record.get("att", NOT_AVAILABLE)

        # extract year from author attribution if present
        year = None
        if author != NOT_AVAILABLE:
            parts = author.split()
            if parts and parts[-1].isdigit():
                year = parts[-1]

        return {
            "organism": record.get("nam", organism_name),
            "author": author,
            "year": year,
            "full_reference": record.get("ref", NOT_AVAILABLE),
        }

    except requests.RequestException as e:
        return {"error": f"Connection error: {e}", "organism": organism_name}
    except json.JSONDecodeError as e:
        return {"error": f"Parse error: {e}", "organism": organism_name}


def query_multiple_species(
    species_list: list[str],
) -> tuple[list[dict], list[str], list[dict]]:
    """
    Query PBDB for multiple species.

    Parameters
    ----------
    species_list : list[str]
        List of species names to query.

    Returns
    -------
    tuple[list[dict], list[str], list[dict]]
        (successful_results, not_found_species, error_results)
    """
    results = []
    not_found = []
    errors = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, species in enumerate(species_list):
        # update progress
        progress = (i + 1) / len(species_list)
        progress_bar.progress(progress)
        status_text.text(f"Querying: {species} ({i + 1}/{len(species_list)})")

        # rate limiting
        if i > 0:
            time.sleep(API_DELAY)

        info = query_pbdb(species.strip())

        if info is None:
            not_found.append(species)
        elif "error" in info:
            errors.append(info)
        else:
            results.append(info)

    progress_bar.empty()
    status_text.empty()

    return results, not_found, errors


def display_single_result(info: dict):
    """
    Display a single species result in a formatted box.

    Parameters
    ----------
    info : dict
        Publication information for a single species.
    """
    with st.container():
        st.markdown('<div class="result-box">', unsafe_allow_html=True)

        col1, col2 = st.columns([1, 3])

        with col1:
            st.write("**Organism:**")
            st.write("**Author:**")
            if info.get("year"):
                st.write("**Year:**")

        with col2:
            st.write(info["organism"])
            st.write(info["author"])
            if info.get("year"):
                st.write(info["year"])

        st.write("**Full Reference:**")
        st.text(info["full_reference"])

        st.markdown("</div>", unsafe_allow_html=True)


def render_header():
    """Render the application header."""
    st.title("PBDB Publication Lookup")
    st.markdown(
        "Query the Paleobiology Database for species publication information"
    )
    st.markdown("---")


def render_single_species_tab():
    """Render the single species lookup interface."""
    st.markdown("### Enter a single species name")

    # single species input
    species_input = st.text_input(
        "Species name",
        placeholder="e.g., Enchodus petrosus",
        help="Enter the scientific name of the species",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        search_button = st.button(
            "Search", key="single_search", use_container_width=True
        )

    if search_button and species_input:
        with st.spinner("Querying PBDB..."):
            result = query_pbdb(species_input)

        handle_single_species_result(result, species_input)


def handle_single_species_result(result: dict | None, species_input: str):
    """
    Handle and display the result of a single species query.

    Parameters
    ----------
    result : dict | None
        Query result from PBDB.
    species_input : str
        The species name that was searched.
    """
    if result is None:
        st.error(f"No publication information found for '{species_input}'")
        st.info(
            "Possible reasons:\n"
            "- The species name may be spelled differently\n"
            "- The species may not be in the database\n"
            "- Try searching without 'cf.' or other qualifiers"
        )
    elif "error" in result:
        st.error(f"Error: {result['error']}")
    else:
        st.success("Found publication information:")
        display_single_result(result)

        # download options
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download as JSON",
                data=json.dumps(result, indent=2),
                file_name=f"{species_input.replace(' ', '_')}.json",
                mime="application/json",
            )
        with col2:
            # format as text
            text_content = f"""Organism: {result["organism"]}
Author: {result["author"]}
Year: {result.get("year", "Not available")}
Full Reference: {result["full_reference"]}"""
            st.download_button(
                label="Download as Text",
                data=text_content,
                file_name=f"{species_input.replace(' ', '_')}.txt",
                mime="text/plain",
            )


def parse_uploaded_file(uploaded_file) -> list[str]:
    """
    Parse species list from uploaded file.

    Parameters
    ----------
    uploaded_file : UploadedFile
        Streamlit uploaded file object.

    Returns
    -------
    list[str]
        List of species names.
    """
    stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
    content = stringio.read()

    species_list = []
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            species_list.append(line)

    return species_list


def render_file_upload_tab():
    """Render the file upload interface for batch processing."""
    st.markdown("### Upload a text file with species names")
    st.info(
        "File format: One species name per line. Lines starting with # are "
        "ignored."
    )

    uploaded_file = st.file_uploader(
        "Choose a text file",
        type=["txt"],
        help="Upload a text file with one species name per line",
    )

    if uploaded_file is not None:
        species_list = parse_uploaded_file(uploaded_file)

        if species_list:
            handle_uploaded_species_list(species_list)
        else:
            st.warning("No valid species names found in file")


def handle_uploaded_species_list(species_list: list[str]):
    """
    Handle processing of uploaded species list.

    Parameters
    ----------
    species_list : list[str]
        List of species names from file.
    """
    st.success(f"Found {len(species_list)} species in file")

    # show species list in expander
    with st.expander("View species list"):
        for sp in species_list:
            st.text(f"- {sp}")

    # search button
    if st.button("Search All Species", key="multi_search"):
        st.markdown("---")
        st.markdown("### Results")

        # query all species
        results, not_found, errors = query_multiple_species(species_list)

        # display results
        display_batch_results(results, not_found, errors, species_list)


def display_batch_summary(total: int, found: int, not_found: int):
    """
    Display summary metrics for batch processing.

    Parameters
    ----------
    total : int
        Total number of species queried.
    found : int
        Number of species found.
    not_found : int
        Number of species not found.
    """
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Queried", total)
    with col2:
        st.metric("Found", found)
    with col3:
        st.metric("Not Found", not_found)


def display_batch_results(
    results: list[dict],
    not_found: list[str],
    errors: list[dict],
    species_list: list[str],
):
    """
    Display results from batch processing.

    Parameters
    ----------
    results : list[dict]
        Successful query results.
    not_found : list[str]
        Species not found in PBDB.
    errors : list[dict]
        Query errors.
    species_list : list[str]
        Original species list.
    """
    # display summary
    display_batch_summary(len(species_list), len(results), len(not_found))

    # display successful results
    if results:
        st.markdown("#### Found Publications")
        for info in results:
            display_single_result(info)

    # display not found species
    if not_found:
        st.markdown("#### Species Not Found in PBDB")
        not_found_text = "\n".join([f"- {sp}" for sp in not_found])
        st.text(not_found_text)

    # display errors
    if errors:
        st.markdown("#### Query Errors")
        for error in errors:
            st.error(f"{error['organism']}: {error['error']}")

    # offer download of all results
    if results or not_found:
        offer_batch_download(results, not_found, errors, len(species_list))


def offer_batch_download(
    results: list[dict], not_found: list[str], errors: list[dict], total: int
):
    """
    Provide download button for batch results.

    Parameters
    ----------
    results : list[dict]
        Successful results.
    not_found : list[str]
        Not found species.
    errors : list[dict]
        Error results.
    total : int
        Total species queried.
    """
    download_data = {
        "found": results,
        "not_found": not_found,
        "errors": [
            {"organism": e["organism"], "error": str(e["error"])}
            for e in errors
        ],
        "summary": {
            "total_queried": total,
            "found_count": len(results),
            "not_found_count": len(not_found),
            "error_count": len(errors),
        },
    }

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download All Results as JSON",
            data=json.dumps(download_data, indent=2),
            file_name="pbdb_results.json",
            mime="application/json",
        )
    with col2:
        # format as text
        text_lines = []
        text_lines.append("PBDB PUBLICATION LOOKUP RESULTS")
        text_lines.append("=" * 35)
        text_lines.append(f"Total Queried: {total}")
        text_lines.append(f"Found: {len(results)}")
        text_lines.append(f"Not Found: {len(not_found)}")
        text_lines.append(f"Errors: {len(errors)}")
        text_lines.append("")

        if results:
            text_lines.append("FOUND PUBLICATIONS:")
            text_lines.append("-" * 19)
            for result in results:
                text_lines.append(f"Organism: {result['organism']}")
                text_lines.append(f"Author: {result['author']}")
                text_lines.append(
                    f"Year: {result.get('year', 'Not available')}"
                )
                text_lines.append(
                    f"Full Reference: {result['full_reference']}"
                )
                text_lines.append("")

        if not_found:
            text_lines.append("NOT FOUND SPECIES:")
            text_lines.append("-" * 18)
            for species in not_found:
                text_lines.append(f"- {species}")
            text_lines.append("")

        if errors:
            text_lines.append("QUERY ERRORS:")
            text_lines.append("-" * 13)
            for error in errors:
                text_lines.append(f"{error['organism']}: {error['error']}")
            text_lines.append("")

        text_content = "\n".join(text_lines)

        st.download_button(
            label="Download All Results as Text",
            data=text_content,
            file_name="pbdb_results.txt",
            mime="text/plain",
        )


def render_footer():
    """Render the application footer with information."""
    st.markdown("---")
    st.markdown("### About")
    st.markdown(
        "This tool queries the "
        "[Paleobiology Database](https://paleobiodb.org) "
        "to retrieve original publication information for species."
    )
    st.markdown(
        "**Note:** A small delay is added between queries to be respectful "
        "to the PBDB API."
    )


def render_main_tabs():
    """Render the main tabbed interface."""
    tab1, tab2 = st.tabs(["Single Species", "Multiple Species (File Upload)"])

    with tab1:
        render_single_species_tab()

    with tab2:
        render_file_upload_tab()


def main():
    """Main application entry point."""
    configure_page()
    render_header()
    render_main_tabs()
    render_footer()


if __name__ == "__main__":
    main()
