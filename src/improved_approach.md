# Improved Approach for Finding Original Taxonomic Descriptions

## Core Problem
Given a taxonomic name, find the original paper that described it (matching the taxonomic authority).

## Current Limitations
- PBDB stores occurrence references, not original descriptions
- Taxonomic authority (e.g., "Cope 1874") doesn't directly link to papers
- CrossRef searches are too broad without exact titles or DOIs

## Recommended Solutions

### 1. Multi-Database Nomenclatural Approach
Query specialized nomenclatural databases in order:

```python
def get_original_description(taxon_name, authority):
    # Try nomenclatural databases first
    sources = [
        query_fossilworks,      # Sister to PBDB, may have type specimens
        query_worms,            # Marine species, includes some fossils
        query_gbif_backbone,    # GBIF Backbone Taxonomy
        query_plazi,            # Taxonomic treatments from literature
        query_bionames,         # Links taxonomic names to literature
        query_itis,             # Integrated Taxonomic Information System
    ]

    for source in sources:
        result = source(taxon_name)
        if result and result.original_publication:
            return result

    # Fallback to current approach
    return crossref_authority_search(taxon_name, authority)
```

### 2. Enhanced CrossRef Search Strategy
Improve CrossRef queries with taxonomic context:

```python
def enhanced_crossref_search(taxon_name, authority, year):
    # Parse authority
    author_parts = authority.replace(year, "").strip()

    # Strategy 1: Search with taxonomic keywords
    query = f"{author_parts} {year} new species genus {taxon_name.split()[0]}"

    # Strategy 2: Search paleontology journals specifically
    journal_filters = [
        "Journal of Paleontology",
        "Palaeontology",
        "Acta Palaeontologica Polonica",
        "Journal of Vertebrate Paleontology",
        "Bulletin of the American Museum"
    ]

    # Strategy 3: Use bibliographic databases
    # Many original descriptions are in old bulletins/monographs
    # that aren't in CrossRef but are in BHL
```

### 3. Build Local Authority Database
Create a curated mapping of common species:

```json
{
  "Tyrannosaurus rex": {
    "authority": "Osborn 1905",
    "doi": "10.1206/0003-0090(2005)295[0001:TAOCD]2.0.CO;2",
    "title": "Tyrannosaurus and other Cretaceous carnivorous dinosaurs",
    "journal": "Bulletin of the American Museum of Natural History",
    "verified": true
  }
}
```

### 4. Type Specimen Approach
Use type specimen databases to find original descriptions:

- Museums often catalog type specimens with original publications
- GBIF has type specimen records with citations
- DiSSCo (Distributed System of Scientific Collections) in Europe

### 5. Specialized Fossil Databases

#### Fossilworks (fossilworks.org)
- Sister project to PBDB
- May have type specimen information
- API: `https://fossilworks.org/bridge.pl`

#### Museum Databases
- AMNH Paleontology Database
- Smithsonian NMNH Paleobiology Collections
- Natural History Museum London Data Portal

### 6. Literature-First Approach
Instead of searching by author/year, search taxonomic literature databases:

```python
def literature_first_search(taxon_name):
    # BHL (Biodiversity Heritage Library)
    # - Contains many old paleontology journals
    # - Has taxonomic name indexing

    # Plazi TreatmentBank
    # - Extracts taxonomic treatments from papers
    # - Links to original publications

    # BioStor
    # - Links taxonomic names to BHL pages
```

## Recommended Implementation Strategy

### Phase 1: Immediate Improvements
1. Add BHL API for old literature (many original descriptions are pre-digital)
2. Implement GBIF Backbone Taxonomy API (has original publication data)
3. Create local cache of verified taxon→DOI mappings

### Phase 2: Enhanced Search
1. Query multiple nomenclatural databases
2. Implement fuzzy matching for author names
3. Add journal-specific search filters

### Phase 3: Machine Learning Approach
1. Train model on known taxon→publication mappings
2. Use NLP to extract taxonomic acts from papers
3. Build confidence scoring for matches

## Example: Better Workflow

```python
def find_original_description(taxon_name):
    # 1. Check local verified database
    if taxon_name in LOCAL_VERIFIED_DB:
        return LOCAL_VERIFIED_DB[taxon_name]

    # 2. Query nomenclatural databases
    result = query_gbif_backbone(taxon_name)
    if result.original_publication_doi:
        return fetch_by_doi(result.original_publication_doi)

    # 3. Search type specimen databases
    type_specimen = query_type_specimens(taxon_name)
    if type_specimen.publication:
        return type_specimen.publication

    # 4. BHL search with taxonomic name recognition
    bhl_result = search_bhl_taxonomic(taxon_name)
    if bhl_result:
        return bhl_result

    # 5. Fallback to current PBDB + CrossRef approach
    return current_approach(taxon_name)
```

## Key Insights

1. **DOIs are not universal**: Many original descriptions predate DOIs (especially for fossils described in 1800s-1900s)

2. **BHL is crucial**: Most fossil original descriptions are in old bulletins/monographs digitized by BHL

3. **Type specimens are key**: The type specimen record usually includes the original publication

4. **Nomenclatural vs Occurrence**: You need nomenclatural databases (track name origins) not occurrence databases (track where fossils are found)

5. **Manual curation needed**: For high-value taxa, manual verification and curation is most reliable

## Recommended Next Steps

1. **Add GBIF API**: GBIF Backbone Taxonomy includes original publication info
2. **Integrate BHL**: Essential for pre-digital literature
3. **Add Plazi**: Extracts taxonomic treatments with citations
4. **Build verification dataset**: Start with common species, manually verify, build from there
5. **Consider WoRMS**: Excellent for marine fossils

The key is to move from occurrence databases (PBDB) to nomenclatural databases (GBIF, WoRMS, Plazi) that actually track original descriptions.