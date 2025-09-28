"""
Streamlit app for finding original taxonomic descriptions.
Uses simplified cache-first approach with persistent parquet storage.
"""

import time

import polars as pl
import streamlit as st

from database_queries import search_taxonomy
from taxonomy_cache import (
    lookup_in_cache,
    save_to_cache,
    load_cache,
    clear_cache,
    get_cache_stats,
)


def configure_page():
    """Configure the Streamlit page settings."""
    st.set_page_config(
        page_title="Taxonomic Reference Finder",
        page_icon="🦴",
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
    st.subheader(f"🔬 {result['search_term']}")

    # check for year mismatch warning
    if result.get("year_mismatch", False):
        st.warning("⚠️ **Year Mismatch Warning**: No reference found with matching publication year. The reference may not be the original taxonomic description.")

    # create two columns
    col1, col2 = st.columns([2, 1])

    with col1:
        # main information
        st.write("**Taxonomic Authority:**", result["taxonomic_authority"] if result["taxonomic_authority"] != "Not available" else "NA")
        st.write("**Year:**", result["year"] or "NA")
        st.write("**Author:**", result["author"] if result["author"] != "Not available" else "NA")

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

        if result["paper_link"] != "Not available":
            st.markdown(f"[📄 View Paper]({result['paper_link']})")


def show_sidebar_stats():
    """Display cache statistics in sidebar."""
    stats = get_cache_stats()

    if stats["count"] > 0:
        st.sidebar.subheader("📊 Cache Statistics")
        st.sidebar.metric("Cached species", stats["count"])

        # source breakdown
        if stats["sources"]:
            st.sidebar.write("**By source:**")
            for source, count in stats["sources"].items():
                st.sidebar.text(f"• {source}: {count}")

        # recent searches
        if stats["recent"]:
            st.sidebar.write("**Recent searches:**")
            for item in stats["recent"][:5]:
                st.sidebar.text(f"• {item['search_term']}")


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
        result["taxonomic_authority"] != "Not available" or
        result["reference"] != "Not available" or
        (result["doi"] != "Not available" and result["doi"] is not None)
    )

    if has_useful_info:
        save_to_cache(result)

    return result


def show_single_search():
    """Show single species search interface."""
    st.subheader("🔍 Single Species Search")

    col1, col2 = st.columns([3, 1])
    with col1:
        species_name = st.text_input(
            "Enter species name:",
            placeholder="e.g., Tyrannosaurus rex",
            key="single_search"
        )
    with col2:
        use_cache = st.checkbox("Use cache", value=True, key="use_cache_single")

    if st.button("Search", type="primary", key="search_single"):
        if species_name:
            with st.spinner(f"Searching for {species_name}..."):
                result = search_species(species_name, use_cache=use_cache)

            st.divider()
            display_result(result)
        else:
            st.warning("Please enter a species name")


def show_batch_search():
    """Show batch search interface."""
    st.subheader("📋 Batch Search")

    # text area for multiple species
    species_text = st.text_area(
        "Enter species names (one per line):",
        height=150,
        placeholder="Tyrannosaurus rex\nEnchodus petrosus\nDiplodocus carnegii"
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        use_cache = st.checkbox("Use cache", value=True, key="use_cache_batch")
    with col2:
        if st.button("Search All", type="primary"):
            if species_text:
                species_list = [line.strip() for line in species_text.split("\n") if line.strip()]

                # progress bar
                progress = st.progress(0)
                status = st.empty()

                results = []
                for i, species in enumerate(species_list):
                    status.text(f"Searching for {species}...")
                    result = search_species(species, use_cache=use_cache)
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
                        mime="text/csv"
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
                key="sort_cache"
            )
        with col2:
            sort_order = st.radio(
                "Order:",
                ["Descending", "Ascending"],
                key="sort_order"
            )
        with col3:
            # filter by source
            sources = cache_df["source"].unique().to_list()
            sources.insert(0, "All")
            source_filter = st.selectbox(
                "Source:",
                sources,
                key="source_filter"
            )

        # apply filters and sorting
        df = cache_df
        if source_filter != "All":
            df = df.filter(pl.col("source") == source_filter)

        df = df.sort(
            sort_by,
            descending=(sort_order == "Descending")
        )

        # limit to 250 rows for display
        display_df = df.limit(250)

        # convert to markdown table with all fields
        markdown_rows = []
        markdown_rows.append("| Search Term | Authority | Year | Author | Reference | DOI | Paper Link | Source | Mismatch | Timestamp |")
        markdown_rows.append("|-------------|-----------|------|--------|-----------|-----|------------|--------|----------|-----------|")

        for row in display_df.to_dicts():
            # safely handle None values and truncate long fields for display
            search_term = str(row["search_term"] or "—")
            search_term = search_term[:30] + "..." if len(search_term) > 30 else search_term

            authority = str(row["taxonomic_authority"] or "—")
            authority = authority[:20] + "..." if len(authority) > 20 else authority

            reference = str(row["reference"] or "—")
            if row.get("year_mismatch", False):
                reference = "⚠️ " + reference[:38] + "..." if len(reference) > 38 else "⚠️ " + reference
            else:
                reference = reference[:40] + "..." if len(reference) > 40 else reference

            doi = str(row["doi"] or "—")
            doi = doi[:20] + "..." if len(doi) > 20 else doi

            paper_link = "🔗" if row["paper_link"] and row["paper_link"] != "Not available" else "—"

            source = str(row["source"] or "—")
            source = source[:15] + "..." if len(source) > 15 else source

            timestamp = str(row["timestamp"])[:16] if row["timestamp"] else "—"

            author = str(row["author"] or "—")

            year_mismatch = "⚠️" if row.get("year_mismatch", False) else "✅"

            markdown_rows.append(f"| {search_term} | {authority} | {row['year'] or '—'} | {author} | {reference} | {doi} | {paper_link} | {source} | {year_mismatch} | {timestamp} |")

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
            mime="text/csv"
        )


def main():
    """Main application function."""
    configure_page()

    st.title("🦴 Taxonomic Reference Finder")
    st.markdown("""
    Find original taxonomic descriptions and publications for species names.
    Results are cached locally in `data/results.parquet` for faster subsequent searches.
    """)

    # sidebar stats
    show_sidebar_stats()

    # main tabs
    tab1, tab2, tab3 = st.tabs(["Single Search", "Batch Search", "View Cache"])

    with tab1:
        show_single_search()

    with tab2:
        show_batch_search()

    with tab3:
        show_cache_view()


if __name__ == "__main__":
    main()