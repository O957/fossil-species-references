"""
Streamlit app for finding original taxonomic descriptions.
Uses simplified cache-first approach with persistent parquet storage.
"""

import polars as pl
import streamlit as st

from database_queries import search_taxonomy
from taxonomy_cache import (
    load_cache,
    lookup_in_cache,
    save_to_cache,
)


def configure_page():
    """Configure the Streamlit page settings."""
    st.set_page_config(
        page_title="Taxonomic Reference Finder",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def display_result(result: dict):
    """
    Display search result in a clean format.

    Parameters
    ----------
    result : dict
        Result dictionary from search.
    """
    st.subheader(f"{result['search_term']}")

    # check for year mismatch warning
    if result.get("year_mismatch", False):
        st.warning(
            "⚠️ **Year Mismatch Warning**: No reference found with matching "
            "publication year. The reference may not be the original "
            "taxonomic description."
        )

    # create two columns
    col1, col2 = st.columns([2, 1])

    with col1:
        # main information
        st.write(
            "**Taxonomic Authority:**",
            result["taxonomic_authority"]
            if result["taxonomic_authority"] != "Not available"
            else "NA",
        )
        st.write("**Year:**", result["year"] or "NA")
        st.write(
            "**Author:**",
            result["author"] if result["author"] != "Not available" else "NA",
        )

        # reference with mismatch indicator
        if result["reference"] != "Not available":
            st.write("**Reference:**")
            st.text(result["reference"])
        elif result.get("year_mismatch", False):
            st.write("**Reference:** ⚠️ No matching reference found")
        else:
            st.write("**Reference:** NA")

    with col2:
        # metadata
        st.write("**Source:**", result["source"])
        if result.get("from_cache"):
            st.success("✅ From cache")
        else:
            st.info("🔍 Fresh search")

        # year mismatch indicator in metadata
        if result.get("year_mismatch", False):
            st.error("⚠️ Year mismatch")

        # links
        if result["doi"] != "Not available":
            st.write("**DOI:**", result["doi"])
        else:
            st.write("**DOI:** NA")

        if result["paper_link"] != "Not available":
            st.markdown(f"[📄 View Paper]({result['paper_link']})")
        else:
            st.write("**Paper Link:** NA")


def search_species(species_name: str, use_cache: bool = True) -> dict:
    """
    Search for species with cache-first approach.

    Parameters
    ----------
    species_name : str
        Species name to search.
    use_cache : bool
        Whether to use cache.

    Returns
    -------
    dict
        Search results.
    """
    # normalize search term
    search_term = species_name.strip()

    # check cache first
    if use_cache:
        cached = lookup_in_cache(search_term)
        if cached:
            cached["from_cache"] = True
            return cached

    # search databases
    result = search_taxonomy(search_term)
    result["from_cache"] = False

    # only save to cache if we found some useful information
    has_useful_info = (
        result["taxonomic_authority"] != "Not available"
        or result["reference"] != "Not available"
        or (result["doi"] != "Not available" and result["doi"] is not None)
    )

    if has_useful_info:
        save_to_cache(result)

    return result


def show_single_search():
    """Show single species search interface."""
    st.subheader("🔍 Single Species Search")

    species_name = st.text_input(
        "Enter species name:",
        placeholder="e.g., Enchodus petrosus",
        key="single_search",
    )

    if st.button("Search", type="primary", key="search_single"):
        if species_name:
            with st.spinner(f"Searching for {species_name}..."):
                result = search_species(species_name, use_cache=True)

            st.divider()
            display_result(result)
        else:
            st.warning("Please enter a species name")


def show_batch_search():
    """Show batch search interface."""
    st.subheader("📋 Batch Search")

    # create example file for download
    example_species = (
        "Stegosaurus stenops\nAmmonites planorbis\nTrilobita paradoxides\n"
        "Archaeopteryx lithographica\nMegalodon carcharocles\nPterodactylus "
        "antiquus\nIchthyosaurus communis\nBrontosaurus excelsus\n"
        "Velociraptor mongoliensis\nMammuthus primigenius"
    )

    # option 1: upload file
    st.write("**Option 1: Upload a text file**")
    uploaded_file = st.file_uploader(
        "Choose a text file with species names (one per line):",
        type=["txt"],
        key="species_file",
    )

    # option 2: manual entry
    st.write("**Option 2: Enter species names manually**")
    species_text = st.text_area(
        "Enter species names (one per line):",
        height=150,
        placeholder="Stegosaurus stenops\nAmmonites planorbis\nTrilobita "
        "paradoxides\nArchaeopteryx lithographica\nMegalodon "
        "carcharocles\nPterodactylus antiquus\nIchthyosaurus communis"
        "\nBrontosaurus excelsus\nVelociraptor mongoliensis\nMammuthus "
        "primigenius",
    )

    # option 3: download example file
    st.write("**Option 3: Download example file**")
    st.download_button(
        label="📥 Download Example File",
        data=example_species,
        file_name="example_species_list.txt",
        mime="text/plain",
        help="Download an example file with fossil species names",
        key="download_example_file",
    )

    # process uploaded file if available
    if uploaded_file is not None:
        try:
            file_content = uploaded_file.read().decode("utf-8")
            species_text = file_content
            species_count = len(
                [line for line in file_content.split("\\n") if line.strip()]
            )
            filename = uploaded_file.name
            st.success(
                f"✅ Loaded {species_count} species from file: {filename}"
            )
        except Exception as e:
            st.error(f"Error reading file: {e}")

    if st.button("Search All", type="primary") and species_text:
        species_list = [
            line.strip() for line in species_text.split("\n") if line.strip()
        ]

        # progress bar
        progress = st.progress(0)
        status = st.empty()

        results = []
        for i, species in enumerate(species_list):
            status.text(f"Searching for {species}...")
            result = search_species(species, use_cache=True)
            results.append(result)
            progress.progress((i + 1) / len(species_list))

        progress.empty()
        status.empty()

        # display results
        st.subheader("Results")
        for result in results:
            with st.expander(f"{result['search_term']} - {result['source']}"):
                display_result(result)

        # option to download results
        if results:
            df = pl.DataFrame(results)
            # remove from_cache column for export
            if "from_cache" in df.columns:
                df = df.drop("from_cache")
            csv = df.write_csv()
            st.download_button(
                label="📥 Download Results (CSV)",
                data=csv,
                file_name="taxonomy_results.csv",
                mime="text/csv",
                key="download_batch_results",
            )


def show_cache_view():
    """Show cache viewer interface."""
    st.subheader("📁 Cached Results")

    cache_df = load_cache()

    if cache_df.is_empty():
        st.info("No cached results yet. Start searching to build the cache!")
    else:
        # sorting options
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            sort_by = st.selectbox(
                "Sort by:",
                ["timestamp", "search_term", "source", "year"],
                key="sort_cache",
            )
        with col2:
            sort_order = st.radio(
                "Order:", ["Descending", "Ascending"], key="sort_order"
            )
        with col3:
            # filter by source
            sources = cache_df["source"].unique().to_list()
            sources.insert(0, "All")
            source_filter = st.selectbox(
                "Source:", sources, key="source_filter"
            )

        # apply filters and sorting
        df = cache_df
        if source_filter != "All":
            df = df.filter(pl.col("source") == source_filter)

        df = df.sort(sort_by, descending=(sort_order == "Descending"))

        # limit to 250 rows for display
        display_df = df.limit(250)

        # convert to markdown table with all fields
        markdown_rows = []
        markdown_rows.append(
            "| Search Term | Authority | Year | Author | Reference | DOI "
            "| Paper Link | Source | Mismatch | Timestamp |"
        )
        markdown_rows.append(
            "|-------------|-----------|------|--------|-----------|-----|"
            "------------|--------|----------|-----------|"
        )

        for row in display_df.to_dicts():
            # safely handle None values and truncate long fields for display
            search_term = str(row["search_term"] or "—")
            search_term = (
                search_term[:30] + "..."
                if len(search_term) > 30
                else search_term
            )

            authority = str(row["taxonomic_authority"] or "NA")
            if authority == "Not available":
                authority = "NA"
            authority = (
                authority[:20] + "..." if len(authority) > 20 else authority
            )

            reference = str(row["reference"] or "NA")
            if reference == "Not available":
                reference = "NA"
            if row.get("year_mismatch", False) and reference != "NA":
                reference = (
                    "⚠️ " + reference[:38] + "..."
                    if len(reference) > 38
                    else "⚠️ " + reference
                )
            else:
                reference = (
                    reference[:40] + "..."
                    if len(reference) > 40
                    else reference
                )

            doi = str(row["doi"] or "NA")
            if doi == "Not available":
                doi = "NA"
            elif doi != "NA":
                # make DOI clickable in markdown
                doi_url = (
                    f"https://doi.org/{doi}"
                    if not doi.startswith("http")
                    else doi
                )
                doi = (
                    f"[{doi[:15]}...]({doi_url})"
                    if len(doi) > 15
                    else f"[{doi}]({doi_url})"
                )
            else:
                doi = doi[:20] + "..." if len(doi) > 20 else doi

            paper_link = str(row["paper_link"] or "NA")
            if paper_link == "Not available":
                paper_link = "NA"
            elif paper_link != "NA":
                # make paper link clickable in markdown
                paper_link = f"[🔗 Link]({paper_link})"
            else:
                paper_link = (
                    paper_link[:30] + "..."
                    if len(paper_link) > 30
                    else paper_link
                )

            source = str(row["source"] or "NA")
            if source == "Not available":
                source = "NA"
            source = source[:15] + "..." if len(source) > 15 else source

            timestamp = (
                str(row["timestamp"])[:16] if row["timestamp"] else "NA"
            )

            author = str(row["author"] or "NA")
            if author == "Not available":
                author = "NA"

            year_mismatch = "⚠️" if row.get("year_mismatch", False) else "✅"
            year_display = row["year"] or "—"

            table_row = (
                f"| {search_term} | {authority} | {year_display} | {author} | "
                f"{reference} | {doi} | {paper_link} | {source} | "
                f"{year_mismatch} | {timestamp} |"
            )
            markdown_rows.append(table_row)

        st.markdown("\n".join(markdown_rows))

        if len(df) > 250:
            st.info(f"Showing first 250 of {len(df)} total entries.")

        # stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total entries", len(df))
        with col2:
            st.metric("Unique species", df["search_term"].n_unique())
        with col3:
            st.metric("Sources used", df["source"].n_unique())

        # download option only
        csv = df.write_csv()
        st.download_button(
            label="📥 Download Cache (CSV)",
            data=csv,
            file_name="taxonomy_cache.csv",
            mime="text/csv",
            key="download_cache_csv",
        )


def main():
    """Main application function."""
    configure_page()

    st.title("Taxonomic Reference Finder")
    st.markdown("""
    Find original taxonomic descriptions and publications for species names.
    Results are cached in `data/results.parquet` for faster subsequent
    searches.
    """)

    # main tabs
    tab1, tab2, tab3 = st.tabs(["Single Search", "Batch Search", "View Cache"])

    with tab1:
        show_single_search()

    with tab2:
        show_batch_search()

    with tab3:
        show_cache_view()

    # footer notes on all pages
    st.markdown("---")
    st.markdown("### How This Works")
    st.markdown("""
    This application searches multiple taxonomic databases including the
    Paleobiology Database (PBDB), GBIF, ZooBank, and WoRMS to find original
    taxonomic authorities and publication references for fossil and modern
    species. When you search for a species, the system first checks the
    local cache for previously retrieved results, then queries each database
    sequentially if no cached data exists. The application uses reference
    validation to ensure that publication years match the taxonomic authority
    years, providing warnings when mismatches occur that might indicate the
    reference is not the original taxonomic description. All successful
    searches are automatically cached to minimize future API calls and provide
    faster responses for repeated queries.
    """)

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
        "this repository:\n"
        "  * e.g. indicating fauna for which no results are return "
        "(see [here]("
        "https://github.com/O957/fossil-species-references/discussions/8)).\n"
        "  * e.g. identifying papers, DOIs, or references for fauna (see "
        "[here]("
        "https://github.com/O957/fossil-species-references/discussions/12)).\n"
        "* Contacting me via email: [my github username]+[@]+[pro]+[ton]+[.]+"
        "[me]"
    )


if __name__ == "__main__":
    main()
