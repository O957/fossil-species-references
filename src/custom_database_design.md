# Custom Taxonomic Database Design

## Why Build Your Own Database?

### Current Problems with API Approach:
- **API timeouts and failures** (WoRMS, ITIS, Plazi often fail)
- **Rate limiting** (BHL requires API keys)
- **Inconsistent data formats** across different sources
- **Network dependency** - app fails without internet
- **Slow performance** - querying 5+ APIs takes 15-20 seconds
- **Data quality issues** - some sources have incomplete/abbreviated references

### Benefits of Custom Database:
- **Lightning fast** - local queries in milliseconds
- **100% reliable** - no network failures
- **Consistent format** - standardized data structure
- **Curated quality** - manually verify important species
- **Handles redescriptions** - multiple references per species
- **Extensible** - add new fields as needed

## Proposed Database Schema

### Core Structure (JSON/Parquet)
```json
{
  "species_name": "Tyrannosaurus rex",
  "genus": "Tyrannosaurus",
  "species": "rex",
  "references": [
    {
      "type": "original_description",
      "author": "Osborn, 1905",
      "year": 1905,
      "full_citation": "Osborn, H.F. 1905. Tyrannosaurus and other Cretaceous carnivorous dinosaurs. Bulletin of the American Museum of Natural History 21:259-265.",
      "doi": "10.1206/0003-0090(2005)295[0001:TAOCD]2.0.CO;2",
      "url": "https://doi.org/10.1206/0003-0090(2005)295[0001:TAOCD]2.0.CO;2",
      "verified": true,
      "source": "manual_curation"
    },
    {
      "type": "redescription",
      "author": "Brochu, 2003",
      "year": 2003,
      "full_citation": "Brochu, C.A. 2003. Osteology of Tyrannosaurus rex: insights from a nearly complete skeleton and high-resolution computed tomographic analysis of the skull. Society of Vertebrate Paleontology Memoir 7:1-138.",
      "doi": "10.1080/02724634.2003.10010947",
      "verified": true,
      "source": "manual_curation"
    }
  ],
  "taxonomic_status": "valid",
  "last_updated": "2024-01-15",
  "data_sources": ["PBDB", "GBIF", "manual_curation"]
}
```

### Alternative: Relational Structure (SQLite)
```sql
-- Species table
CREATE TABLE species (
    id INTEGER PRIMARY KEY,
    species_name TEXT UNIQUE NOT NULL,
    genus TEXT NOT NULL,
    species TEXT NOT NULL,
    taxonomic_status TEXT DEFAULT 'valid',
    last_updated DATE,
    INDEX(species_name),
    INDEX(genus)
);

-- References table
CREATE TABLE references (
    id INTEGER PRIMARY KEY,
    species_id INTEGER,
    reference_type TEXT, -- 'original_description', 'redescription', 'revision'
    author TEXT NOT NULL,
    year INTEGER NOT NULL,
    full_citation TEXT NOT NULL,
    doi TEXT,
    url TEXT,
    verified BOOLEAN DEFAULT FALSE,
    source TEXT, -- 'PBDB', 'GBIF', 'manual_curation'
    confidence REAL DEFAULT 1.0,
    FOREIGN KEY(species_id) REFERENCES species(id)
);
```

## Implementation Strategy

### Phase 1: Bootstrap from Existing Data
```python
def bootstrap_database():
    """Create initial database from PBDB dataset + nomenclatural sources."""

    # 1. Load PBDB data as base
    pbdb_df = pl.read_parquet("../data/pbdb_essential_taxonomy_with_refs.parquet")

    # 2. For each species in PBDB:
    species_db = []
    for row in pbdb_df.iter_rows(named=True):
        species_entry = {
            "species_name": row["nam"],
            "genus": row["nam"].split()[0] if " " in row["nam"] else row["nam"],
            "species": row["nam"].split()[1] if " " in row["nam"] else "",
            "references": [{
                "type": "occurrence_reference",  # Note: may not be original
                "author": row["att"],
                "year": extract_year(row["att"]),
                "full_citation": row["ref"],
                "doi": row.get("doi"),
                "verified": False,
                "source": "PBDB",
                "confidence": 0.6  # Lower confidence - may not be original
            }],
            "taxonomic_status": "valid",
            "data_sources": ["PBDB"]
        }
        species_db.append(species_entry)

    return species_db
```

### Phase 2: Enhance with Nomenclatural Data
```python
def enhance_with_nomenclatural_sources(species_db):
    """Enhance database with verified nomenclatural sources."""

    for entry in species_db:
        species_name = entry["species_name"]

        # Check GBIF for original publication
        gbif_result = query_gbif_backbone(species_name)
        if gbif_result and gbif_result.get("publishedIn"):
            entry["references"].append({
                "type": "original_description",
                "author": gbif_result["authorship"],
                "year": gbif_result["year"],
                "full_citation": gbif_result["publishedIn"],
                "verified": True,
                "source": "GBIF",
                "confidence": 0.9
            })
            entry["data_sources"].append("GBIF")
```

### Phase 3: Manual Curation for High-Value Species
```python
# Create a curation interface
def create_curation_interface():
    """Streamlit app for manual curation of important species."""

    important_species = [
        "Tyrannosaurus rex", "Triceratops horridus", "Velociraptor mongoliensis",
        "Archaeopteryx lithographica", "Homo sapiens", "Homo neanderthalensis"
    ]

    for species in important_species:
        st.write(f"Curating: {species}")

        # Show current data
        current_refs = get_species_references(species)
        st.json(current_refs)

        # Allow manual editing
        new_ref = st.text_area(f"Add/edit reference for {species}")
        if st.button(f"Update {species}"):
            update_species_reference(species, new_ref)
```

## Database Storage Options

### Option 1: JSON + Polars (Recommended)
```python
# Fast, simple, version-controllable
species_db = pl.DataFrame(species_data)
species_db.write_parquet("taxonomic_database.parquet")

# Query examples
def find_species(name):
    return species_db.filter(pl.col("species_name") == name)

def find_by_author(author):
    return species_db.filter(
        pl.col("references").list.eval(
            pl.element().struct.field("author").str.contains(author)
        ).list.any()
    )
```

### Option 2: SQLite (For complex queries)
```python
import sqlite3

def query_species_with_redescriptions():
    """Find species with multiple references."""
    return conn.execute("""
        SELECT s.species_name, COUNT(r.id) as ref_count
        FROM species s
        JOIN references r ON s.id = r.species_id
        GROUP BY s.species_name
        HAVING ref_count > 1
        ORDER BY ref_count DESC
    """).fetchall()
```

## Advantages for Your Use Case

### 1. **Handles Redescriptions Perfectly**
```json
{
  "species_name": "Velociraptor mongoliensis",
  "references": [
    {
      "type": "original_description",
      "author": "Osborn, 1924",
      "full_citation": "Osborn, H.F. 1924. Three new Theropoda, Protoceratops zone, central Mongolia. American Museum Novitates 144:1-12."
    },
    {
      "type": "redescription",
      "author": "Norell & Makovicky, 1999",
      "full_citation": "Norell, M.A. & Makovicky, P.J. 1999. Important features of the dromaeosaurid skeleton II: information from newly collected specimens of Velociraptor mongoliensis. American Museum Novitates 3282:1-45."
    }
  ]
}
```

### 2. **Lightning Fast Performance**
- **Local queries**: ~1ms vs 15-20s for API calls
- **No network dependency**: Works offline
- **Batch processing**: Handle thousands of species instantly

### 3. **Quality Control**
- **Verification flags**: Mark manually verified entries
- **Confidence scores**: Track data reliability
- **Source tracking**: Know where each reference came from
- **Version control**: Track changes over time

## Migration Path

### Week 1: Bootstrap
- Convert PBDB data to new format
- Add GBIF data where available
- Create basic query interface

### Week 2: Enhance
- Add WoRMS data for marine species
- Implement CrossRef DOI lookup for existing references
- Create data validation scripts

### Week 3: Curate
- Manually verify top 100 most important species
- Add missing original descriptions
- Create curation workflow

### Week 4: Deploy
- Replace API calls with database queries
- Update Streamlit app to use local database
- Add database management interface

## Implementation Example

```python
class TaxonomicDatabase:
    def __init__(self, db_path="taxonomic_database.parquet"):
        self.db = pl.read_parquet(db_path)

    def find_original_description(self, species_name):
        """Find the original description for a species."""
        result = self.db.filter(pl.col("species_name") == species_name)

        if len(result) == 0:
            return None

        references = result[0]["references"]

        # Look for original description first
        for ref in references:
            if ref["type"] == "original_description":
                return ref

        # Fallback to highest confidence reference
        return max(references, key=lambda x: x.get("confidence", 0))

    def find_all_references(self, species_name):
        """Get all references for a species."""
        result = self.db.filter(pl.col("species_name") == species_name)
        return result[0]["references"] if len(result) > 0 else []

    def search_by_author(self, author_name):
        """Find all species described by an author."""
        # Complex nested search in Polars
        return self.db.filter(
            pl.col("references").list.eval(
                pl.element().struct.field("author").str.contains(author_name)
            ).list.any()
        )

# Usage
db = TaxonomicDatabase()
original = db.find_original_description("Tyrannosaurus rex")
print(original["full_citation"])
# "Osborn, H.F. 1905. Tyrannosaurus and other Cretaceous carnivorous dinosaurs..."
```

## Recommendation

**Yes, absolutely build your own database!** The API approach is a proof-of-concept, but a curated local database would be:

1. **10x faster** (milliseconds vs seconds)
2. **100x more reliable** (no network failures)
3. **Better data quality** (manual curation)
4. **Handles your specific needs** (redescriptions, multiple authorities)

Start with the PBDB data as your foundation, enhance with GBIF where available, and manually curate the most important species. You'll have a production-ready system that actually works consistently.