"""
Simplified Streamlit app for finding original taxonomic descriptions.
Uses the unified taxonomy search system with persistent caching.
"""

import streamlit as st
import polars as pl
from pathlib import Path

from unified_taxonomy_search import unified_taxonomy_search, TaxonomyCache


def configure_page():
    """Configure the Streamlit page settings."""
    st.set_page_config(
        page_title="Taxonomic Reference Finder",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def display_result(result: dict):
    """
    Display search result in a clean format.

    Parameters
    ----------
    result : dict
        Result from unified_taxonomy_search.
    """
    st.subheader(f"🔬 {result['search_term']}")

    # create two columns
    col1, col2 = st.columns([2, 1])

    with col1:
        # main information
        st.write("**Taxonomic Authority:**", result["taxonomic_authority"])
        st.write("**Year:**", result["year"] or "Not available")
        st.write("**Author:**", result["author"])

        # reference
        if result["reference"] != "Not available":
            st.write("**Reference:**")
            st.text(result["reference"])

    with col2:
        # metadata
        st.write("**Source:**", result["source"])
        if result.get("from_cache"):
            st.success("✅ From cache")
        else:
            st.info("🔍 Fresh search")

        # links
        if result["doi"] != "Not available":
            st.write("**DOI:**", result["doi"])

        if result["paper_link"] != "Not available":
            st.markdown(f"[📄 View Paper]({result['paper_link']})")


def show_cache_stats():
    """Display cache statistics in sidebar."""
    cache = TaxonomyCache()

    if not cache.cache_df.is_empty():
        st.sidebar.subheader("📊 Cache Statistics")
        st.sidebar.metric("Cached species", len(cache.cache_df))

        # most recent searches
        recent = cache.cache_df.sort("timestamp", descending=True).limit(5)
        if not recent.is_empty():
            st.sidebar.write("**Recent searches:**")
            for row in recent.to_dicts():
                st.sidebar.text(f"• {row['search_term']}")


def show_batch_search():
    """Show batch search interface."""
    st.subheader("📋 Batch Search")

    # text area for multiple species
    species_text = st.text_area(
        "Enter species names (one per line):",
        height=150,
        placeholder="Tyrannosaurus rex\nEnchodus petrosus\nDiplodocus carnegii"
    )

    if st.button("Search All", type="primary"):
        if species_text:
            species_list = [line.strip() for line in species_text.split("\n") if line.strip()]

            # progress bar
            progress = st.progress(0)
            status = st.empty()

            results = []
            for i, species in enumerate(species_list):
                status.text(f"Searching for {species}...")
                result = unified_taxonomy_search(species)
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
                csv = df.write_csv()
                st.download_button(
                    label="📥 Download Results (CSV)",
                    data=csv,
                    file_name="taxonomy_results.csv",
                    mime="text/csv"
                )


def main():
    """Main application function."""
    configure_page()

    st.title("🦴 Taxonomic Reference Finder")
    st.markdown("""
    Find original taxonomic descriptions and publications for species names.
    Results are cached locally for faster subsequent searches.
    """)

    # sidebar
    show_cache_stats()

    # search mode selection
    tab1, tab2, tab3 = st.tabs(["Single Search", "Batch Search", "View Cache"])

    with tab1:
        # single species search
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
                    result = unified_taxonomy_search(species_name, use_cache=use_cache)

                st.divider()
                display_result(result)
            else:
                st.warning("Please enter a species name")

    with tab2:
        show_batch_search()

    with tab3:
        # view full cache
        st.subheader("📁 Cached Results")

        cache = TaxonomyCache()

        if cache.cache_df.is_empty():
            st.info("No cached results yet. Start searching to build the cache!")
        else:
            # sorting options
            col1, col2 = st.columns([2, 1])
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

            # display cache
            df = cache.cache_df.sort(
                sort_by,
                descending=(sort_order == "Descending")
            )

            # show in dataframe
            st.dataframe(
                df.select([
                    "search_term",
                    "taxonomic_authority",
                    "year",
                    "source",
                    "doi",
                    "timestamp"
                ]),
                use_container_width=True
            )

            # download option
            csv = df.write_csv()
            st.download_button(
                label="📥 Download Full Cache (CSV)",
                data=csv,
                file_name="taxonomy_cache.csv",
                mime="text/csv"
            )

            # clear cache option
            if st.button("🗑️ Clear Cache", type="secondary"):
                if st.checkbox("Are you sure?"):
                    cache.cache_df = pl.DataFrame(schema={
                        "search_term": pl.Utf8,
                        "taxonomic_authority": pl.Utf8,
                        "year": pl.Int64,
                        "author": pl.Utf8,
                        "reference": pl.Utf8,
                        "doi": pl.Utf8,
                        "paper_link": pl.Utf8,
                        "source": pl.Utf8,
                        "timestamp": pl.Datetime,
                    })
                    cache.cache_df.write_parquet(str(cache.cache_file))
                    st.success("Cache cleared!")
                    st.rerun()


if __name__ == "__main__":
    main()