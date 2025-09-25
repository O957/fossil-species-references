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
        Dictionary containing publication info, error
        info, or None if not found.
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

        # show warning if there's a mismatch
        if info.get("attribution_mismatch"):
            st.warning(
                f"⚠️ **Note:** The taxonomic authority {info['author']} "
                "does not match "
                f"the reference below ({info.get('ref_author', 'N/A')}). "
                f"The original describing paper by {info['author']} may not "
                "be available in PBDB."
            )

        col1, col2 = st.columns([1, 3])

        with col1:
            st.write("**Organism:**")
            st.write("**Taxonomic Authority:**")
            if info.get("year"):
                st.write("**Year:**")

        with col2:
            st.write(info["organism"])
            st.write(info["author"])
            if info.get("year"):
                st.write(info["year"])

        st.write("**Reference in PBDB:**")
        st.text(info["full_reference"])

        st.markdown("</div>", unsafe_allow_html=True)


def render_header():
    """Render the application header."""
    st.title("Species Reference Publication Lookup")
    st.markdown(
        "_Query the Paleobiology Database for species publication "
        "information._"
    )


def render_single_species_tab():
    """
    Render the single species lookup interface.
    """
    st.markdown("### Enter A Single Species Name")

    # single species input
    species_input = st.text_input(
        "Species Name",
        placeholder="e.g., Enchodus petrosus",
        help="Enter the scientific name of the species.",
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
    st.markdown("### Upload Text File With Species Names")
    st.info(
        "File format: One species name per line. Lines starting with # are "
        "ignored."
    )

    uploaded_file = st.file_uploader(
        "Choose Text File",
        type=["txt"],
        help="Upload a text file with one species name per line.",
    )

    # example file content
    with st.expander("📋 Example File Format"):
        st.markdown("**Copy this example content to create your own file:**")
        example_content = """# Example fossil species list
# Lines starting with # are ignored as comments
Tyrannosaurus rex
Triceratops horridus
Allosaurus fragilis
Stegosaurus stenops
Brontosaurus excelsus
Diplodocus carnegii
Archaeopteryx lithographica
Ichthyosaurus communis
Plesiosaaurus dolichodeirus
Ammonites bisulcatus"""
        st.code(example_content, language="text")
        st.download_button(
            label="📥 Download Example File",
            data=example_content,
            file_name="example_species_list.txt",
            mime="text/plain",
            help="Download this example as a text file",
        )

    if uploaded_file is not None:
        species_list = parse_uploaded_file(uploaded_file)

        if species_list:
            handle_uploaded_species_list(species_list)
        else:
            st.warning("No valid species names found in file.")


def handle_uploaded_species_list(species_list: list[str]):
    """
    Handle processing of uploaded species list.

    Parameters
    ----------
    species_list : list[str]
        List of species names from file.
    """
    st.success(f"Found {len(species_list)} species in file.")

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
    st.markdown("### Notes")
    st.markdown(
        "This tool queries the "
        "[Paleobiology Database](https://paleobiodb.org) "
        "to retrieve original publication information for species.\n\n"
        "The repository for this application can be found here: "
        "<https://github.com/O957/fossil-species-references>.\n\n"
        "The license for this application: "
        "<https://github.com/O957/fossil-species-references/blob/main/LICENSE>"
    )
    st.markdown(
        "**NOTE** A small delay is added between queries to be respectful "
        "to the PBDB API."
    )
    st.markdown(
        "__How may I contribute to this project?__\n"
        "* Making an [issue]("
        "https://github.com/O957/fossil-species-references/issues) (comment, "
        "feature, bug) in this repository.\n"
        "* Making a [pull request]("
        "https://github.com/O957/fossil-species-references/pulls) to this "
        "repository.\n"
        "* Engaging in a [discussion thread]("
        "https://github.com/O957/fossil-species-references/discussions) in "
        "this repository.\n"
        "* Contacting me via email: [my github username]+[@]+[pro]+[ton]+[.]+"
        "[me]"
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
