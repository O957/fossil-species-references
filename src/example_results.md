# Database Search Results for Scapanorhynchus

## GBIF

**Fields returned:**
- **taxonomic_authority**: Woodward, 1889
- **reference**: Cat. Foss. Fish. Brit. Mus., 1
- **year**: 1889
- **author**: Woodward
- **doi**: Not available
- **source**: GBIF

## ZooBank

No results found.

## PBDB

**Fields returned:**
- **taxonomic_authority**: Woodward 1889
- **reference**: A. S. Woodward. 1889. Catalogue of the Fossil Fishes in the British Museum (Natural History) Part 1. Catalogue of the Fossil Fishes in the British Museum (Natural History) 1:1-613
- **year**: 1889
- **author**: Woodward
- **doi**: None
- **source**: PBDB

## WoRMS

**Fields returned:**
- **taxonomic_authority**: Woodward, 1889
- **reference**: Froese, R. and D. Pauly. Editors. (2025). FishBase. Scapanorhynchus Woodward, 1889. Accessed through: World Register of Marine Species at: https://www.marinespecies.org/aphia.php?p=taxdetails&id=297746 on 2025-09-28
- **year**: 1889
- **author**: Woodward
- **doi**: Not available
- **source**: WoRMS

## Unified Search Result

**Final combined result from all databases:**
- **search_term**: Scapanorhynchus
- **taxonomic_authority**: Woodward, 1889
- **year**: 1889
- **author**: Woodward
- **reference**: A. S. Woodward. 1889. Catalogue of the Fossil Fishes in the British Museum (Natural History) Part 1. Catalogue of the Fossil Fishes in the British Museum (Natural History) 1:1-613
- **doi**: None
- **paper_link**: Not available
- **source**: GBIF (ref: PBDB)

## Smart Reference Selection Logic

The system now uses intelligent scoring to choose the best reference:

### Scoring Criteria:
1. **Year Matching**: References containing the taxonomic authority year get priority
2. **PBDB Bonus**: +1000 points (PBDB typically has the best original references for fossils)
3. **Database Citation Penalty**: -500 points for modern database citations (containing "accessed through", "fishbase", "world register", "editors", "database")
4. **Length Bonus**: +1 point per character (longer references usually more complete)

### Scoring Results for Scapanorhynchus:
- **PBDB**: Score 1179 (1000 PBDB bonus + 179 length)
- **WoRMS**: Score -285 (215 length - 500 database penalty)
- **GBIF**: Score 0 (doesn't contain year 1889)

### Final Selection:
**PBDB wins** with the complete original citation: "A. S. Woodward. 1889. Catalogue of the Fossil Fishes in the British Museum (Natural History) Part 1..."

This ensures users get the actual original publication reference rather than modern database citations, while prioritizing PBDB as the most reliable source for paleontological references when available.