"""
Enhanced Streamlit web application for PBDB Publication
Lookup with reference resolution. This app allows users to
query the Paleobiology Database for publication information
about species, and automatically attempts to resolve
missing original references.
"""

import json
from io import StringIO

import streamlit as st

# import our enhanced functions
from enhanced_query_functions import (
    enhanced_query_pbdb,
    query_multiple_species_enhanced,
)
from pbdb_publication_lookup import normalize_taxonomic_authority


def configure_page():
    """
    Configure Streamlit page settings.
    """
    st.set_page_config(
        page_title="Enhanced PBDB Publication Lookup",
        page_icon="🔍",
        layout="wide",
    )


def display_enhanced_single_result(info: dict):
    """
    Display a single species result with enhanced reference information.

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
            st.write(normalize_taxonomic_authority(info["author"]))
            if info.get("year"):
                st.write(info["year"])

        st.write("**Reference in PBDB:**")
        st.text(info["full_reference"])

        # show external reference if found (always show if available)
        if info.get("external_reference"):
            ext = info["external_reference"]

            # if there's a mismatch, call it the original reference
            if info.get("attribution_mismatch"):
                st.success(
                    f"✅ **Original Reference Found** (via {ext['source']}):"
                )
            else:
                st.info(
                    f"🔗 **External Reference Found** (via {ext['source']}):"
                )

            st.text(ext["formatted_citation"])

            # add links if available
            col_doi, col_url = st.columns(2)
            if ext.get("doi"):
                with col_doi:
                    st.markdown(
                        f"[📄 View Paper](https://doi.org/{ext['doi']})"
                    )
            if ext.get("url"):
                with col_url:
                    st.markdown(f"[🔗 External Link]({ext['url']})")

        # show additional context for mismatches
        if info.get("attribution_mismatch"):
            if info.get("validation_failed"):
                st.info(
                    "ℹ️ **External reference found but did not match PBDB "
                    "reference** - hiding potentially unrelated paper to "
                    "avoid confusion."
                )
            elif info.get("resolution_attempted"):
                st.info(
                    "🔍 **Reference Resolution Attempted**: Could not locate "
                    "the original paper in external databases."
                )

        st.markdown("</div>", unsafe_allow_html=True)


def render_header():
    """Render the application header."""
    st.title("Enhanced Species Reference Publication Lookup")
    st.markdown(
        "_Query the Paleobiology Database for species publication information "
        "with automatic resolution of missing original references._"
    )


def render_settings_sidebar():
    """
    Render the settings sidebar.

    Returns
    -------
    dict
        Settings configuration.
    """
    st.sidebar.header("⚙️ Settings")

    # reference resolution settings
    enable_resolution = st.sidebar.checkbox(
        "Enable Reference Resolution",
        value=True,
        help=(
            "Automatically search for original references when PBDB has "
            "mismatches"
        ),
    )

    # api key input
    bhl_api_key = st.sidebar.text_input(
        "BHL API Key (Optional)",
        type="password",
        help=(
            "Biodiversity Heritage Library API key for better historical "
            "reference coverage"
        ),
    )

    # info about external sources
    with st.sidebar.expander("ℹ️ External Sources"):
        st.markdown("""
        When enabled, the system searches:
        - **CrossRef**: Modern papers with DOIs
        - **WoRMS**: Marine species authorities
        - **BHL**: Historical biodiversity literature
        """)

    return {
        "enable_resolution": enable_resolution,
        "bhl_api_key": bhl_api_key if bhl_api_key else None,
    }


def render_single_species_tab(settings: dict):
    """
    Render the single species lookup interface.

    Parameters
    ----------
    settings : dict
        Application settings.
    """
    st.markdown("### Enter A Single Species Name")

    # single species input
    species_input = st.text_input(
        "Species Name",
        placeholder="e.g., Enchodus petrosus, Squalicorax",
        help="Enter the scientific name of the species.",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        search_button = st.button(
            "Search", key="single_search", use_container_width=True
        )

    if search_button and species_input:
        with st.spinner("Searching local PBDB dataset and resolving references..."):
            result = enhanced_query_pbdb(
                species_input,
                resolve_missing=settings["enable_resolution"],
                bhl_api_key=settings["bhl_api_key"],
            )

        handle_single_species_result(result, species_input, settings)


def handle_single_species_result(
    result: dict, species_input: str, settings: dict
):
    """
    Handle and display the result of a single species query.

    Parameters
    ----------
    result : dict
        Query result from enhanced PBDB query.
    species_input : str
        The species name that was searched.
    settings : dict
        Application settings.
    """
    if "error" in result:
        if "No records found" in result["error"]:
            st.error(f"No publication information found for '{species_input}' in local PBDB dataset")
            st.info(
                "Possible reasons:\n"
                "- The species name may be spelled differently\n"
                "- The species may not be in the local dataset\n"
                "- Try searching without 'cf.' or other qualifiers"
            )
        else:
            st.error(f"Error: {result['error']}")
    else:
        st.success("Found publication information:")
        display_enhanced_single_result(result)

        # download options
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download as JSON",
                data=json.dumps(result, indent=2),
                file_name=f"{species_input.replace(' ', '_')}_enhanced.json",
                mime="application/json",
            )
        with col2:
            # format as text
            text_content = format_result_as_text(result)
            st.download_button(
                label="Download as Text",
                data=text_content,
                file_name=f"{species_input.replace(' ', '_')}_enhanced.txt",
                mime="text/plain",
            )


def format_result_as_text(result: dict) -> str:
    """
    Format result as text content.

    Parameters
    ----------
    result : dict
        Result dictionary.

    Returns
    -------
    str
        Formatted text content.
    """
    lines = [
        f"Organism: {result['organism']}",
        f"Taxonomic Authority: {normalize_taxonomic_authority(result['author'])}",
        f"Year: {result.get('year', 'Not available')}",
        "",
        "PBDB Reference:",
        result["full_reference"],
    ]

    # show external reference if found
    if result.get("external_reference"):
        ext = result["external_reference"]
        lines.extend(
            [
                "",
                f"🔗 External Reference Found (via {ext['source']}):",
                ext["formatted_citation"],
            ]
        )

        if ext.get("doi"):
            lines.append(f"DOI: {ext['doi']}")
        if ext.get("url"):
            lines.append(f"URL: {ext['url']}")

    if result.get("attribution_mismatch"):
        lines.extend(
            [
                "",
                "⚠️ Attribution Mismatch Detected:",
                f"   Taxonomic Authority: {result['author']}",
                f"   PBDB Reference: {result.get('ref_author', 'N/A')} "
                f"{result.get('ref_year', 'N/A')}",
            ]
        )

        if result.get("external_reference"):
            lines.append(
                "   The external reference above is likely the original "
                "describing paper."
            )
        elif result.get("validation_failed"):
            lines.extend(
                [
                    "",
                    (
                        "ℹ️ External reference found but did not match PBDB "
                        "reference"
                    ),
                    "   Hiding potentially unrelated paper to avoid confusion",
                ]
            )
        elif result.get("resolution_attempted"):
            lines.extend(
                [
                    "",
                    (
                        "❌ Could not locate original reference in external "
                        "sources"
                    ),
                ]
            )

    return "\n".join(lines)


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


def render_file_upload_tab(settings: dict):
    """
    Render the file upload interface for batch processing.

    Parameters
    ----------
    settings : dict
        Application settings.
    """
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
Squalicorax
Enchodus petrosus
Allosaurus fragilis"""
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
            handle_uploaded_species_list(species_list, settings)
        else:
            st.warning("No valid species names found in file.")


def handle_uploaded_species_list(species_list: list[str], settings: dict):
    """
    Handle processing of uploaded species list.

    Parameters
    ----------
    species_list : list[str]
        List of species names from file.
    settings : dict
        Application settings.
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

        # query all species with enhanced resolution
        results, not_found, errors = query_multiple_species_enhanced(
            species_list,
            resolve_missing=settings["enable_resolution"],
            bhl_api_key=settings["bhl_api_key"],
            show_progress=False,  # streamlit will show progress
        )

        # display results
        display_batch_results(results, not_found, errors, species_list)


def display_batch_summary(
    total: int, found: int, not_found: int, resolved: int
):
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
    resolved : int
        Number of species with resolved references.
    """
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Queried", total)
    with col2:
        st.metric("Found", found)
    with col3:
        st.metric("Not Found", not_found)
    with col4:
        st.metric("References Resolved", resolved)


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
    # count resolved references
    resolved_count = sum(1 for r in results if r.get("original_reference"))

    # display summary
    display_batch_summary(
        len(species_list), len(results), len(not_found), resolved_count
    )

    # display successful results
    if results:
        st.markdown("#### Found Publications")
        for info in results:
            display_enhanced_single_result(info)

    # display not found species
    if not_found:
        st.markdown("#### Species Not Found in Local PBDB Dataset")
        not_found_text = "\n".join([f"- {sp}" for sp in not_found])
        st.text(not_found_text)

    # display errors
    if errors:
        st.markdown("#### Query Errors")
        for error in errors:
            st.error(f"{error['organism']}: {error['error']}")

    # offer download of all results
    if results or not_found:
        offer_enhanced_batch_download(
            results, not_found, errors, len(species_list)
        )


def offer_enhanced_batch_download(
    results: list[dict], not_found: list[str], errors: list[dict], total: int
):
    """
    Provide download button for enhanced batch results.

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
    resolved_count = sum(1 for r in results if r.get("original_reference"))

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
            "resolved_references": resolved_count,
        },
    }

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download All Results as JSON",
            data=json.dumps(download_data, indent=2),
            file_name="enhanced_pbdb_results.json",
            mime="application/json",
        )
    with col2:
        # format as text
        text_content = format_batch_results_as_text(
            results, not_found, errors, total, resolved_count
        )
        st.download_button(
            label="Download All Results as Text",
            data=text_content,
            file_name="enhanced_pbdb_results.txt",
            mime="text/plain",
        )


def format_batch_results_as_text(
    results: list[dict],
    not_found: list[str],
    errors: list[dict],
    total: int,
    resolved_count: int,
) -> str:
    """
    Format batch results as text.

    Parameters
    ----------
    results : list[dict]
        Successful results.
    not_found : list[str]
        Not found species.
    errors : list[dict]
        Error results.
    total : int
        Total queried.
    resolved_count : int
        Number of resolved references.

    Returns
    -------
    str
        Formatted text content.
    """
    text_lines = []
    text_lines.append("ENHANCED PBDB PUBLICATION LOOKUP RESULTS")
    text_lines.append("=" * 45)
    text_lines.append(f"Total Queried: {total}")
    text_lines.append(f"Found: {len(results)}")
    text_lines.append(f"Not Found: {len(not_found)}")
    text_lines.append(f"Errors: {len(errors)}")
    text_lines.append(f"References Resolved: {resolved_count}")
    text_lines.append("")

    if results:
        text_lines.append("FOUND PUBLICATIONS:")
        text_lines.append("-" * 19)
        for result in results:
            text_lines.append(format_result_as_text(result))
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

    return "\n".join(text_lines)


def render_footer():
    """Render the application footer with information."""
    st.markdown("---")
    st.markdown("### How This Works")
    st.markdown(
        "This application searches a local PBDB dataset (parquet file with ~450K records) for species information. "
        'When the data shows a taxonomic authority (like "Whitley 1939") but references a different paper '
        "(like \"Sepkoski 2002\"), it indicates the original describing paper isn't in the dataset. "
        "In these cases, our system automatically searches external online sources—CrossRef for modern papers with DOIs, "
        "Biodiversity Heritage Library for historical taxonomic literature, and World Register of Marine Species "
        "for marine taxa—to locate and display the original publication where the species was first described, "
        "providing researchers with access to the complete taxonomic citation history."
    )
    st.markdown("---")
    st.markdown("### About This Enhanced Version")
    st.markdown(
        "The original application repository: "
        "<https://github.com/O957/fossil-species-references>"
    )


def render_main_tabs(settings: dict):
    """
    Render the main tabbed interface.

    Parameters
    ----------
    settings : dict
        Application settings.
    """
    tab1, tab2 = st.tabs(["Single Species", "Multiple Species (File Upload)"])

    with tab1:
        render_single_species_tab(settings)

    with tab2:
        render_file_upload_tab(settings)


def main():
    """Main application entry point."""
    configure_page()
    render_header()

    # render settings sidebar and get configuration
    settings = render_settings_sidebar()

    # render main interface
    render_main_tabs(settings)
    render_footer()


if __name__ == "__main__":
    main()
