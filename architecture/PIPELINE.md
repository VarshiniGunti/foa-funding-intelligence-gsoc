# FOA Ingestion Pipeline Architecture

## Overview

The FOA ingestion pipeline is a modular system that transforms raw FOA URLs into structured, tagged funding data. The pipeline follows a clear separation of concerns with three main components.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         FOA URL Input                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FOAExtractor.fetch_url()                      │
│  • HTTP GET request with timeout and error handling             │
│  • Returns raw HTML content                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              FOAPipeline.process_url() - Router                  │
│  • Detects FOA source (Grants.gov, NSF, etc.)                   │
│  • Routes to appropriate parser                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
        ┌──────────────┐ ┌──────────┐ ┌──────────┐
        │ Grants.gov   │ │   NSF    │ │ Generic  │
        │   Parser     │ │  Parser  │ │  Parser  │
        └──────────────┘ └──────────┘ └──────────┘
                │            │            │
                └────────────┼────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Field Extraction & Normalization                │
│  • Extract: title, agency, dates, eligibility, award range      │
│  • Normalize: ISO 8601 dates, currency amounts, text            │
│  • Generate: FOA ID if missing (UUID-based)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SemanticTagger.tag()                          │
│  • Keyword matching across 4 tag categories                      │
│  • Research domains (AI, Biology, Climate, etc.)                │
│  • Methods (Computational, Experimental, etc.)                  │
│  • Populations (Students, Underrepresented, etc.)               │
│  • Sponsor themes (Innovation, Collaboration, etc.)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FOAPipeline Export                            │
│  • JSON export: Full structured data                             │
│  • CSV export: Tabular format for spreadsheets                  │
│  • Create output directory if needed                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Output Files                                  │
│  • foa.json: Structured FOA data with semantic tags             │
│  • foa.csv: Tabular format for analysis                         │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. FOAExtractor

**Responsibility**: Fetch and parse FOA content from various sources

**Key Methods**:
- `fetch_url(url)`: HTTP retrieval with error handling
  - Timeout: 10 seconds
  - User-Agent header for compatibility
  - Returns raw HTML or None on failure

- `parse_grants_gov(html, url)`: Grants.gov-specific parsing
  - Extracts title from H1/H2 tags
  - Parses FOA ID from URL or content
  - Finds dates using regex patterns
  - Extracts agency, award range, program description

- `parse_nsf(html, url)`: NSF-specific parsing
  - Sets agency to "National Science Foundation"
  - Extracts NSF solicitation number
  - Parses dates and award amounts
  - Handles NSF-specific HTML structure

- `_format_date(date_tuple)`: Normalizes dates to ISO 8601
  - Converts (month, day, year) to YYYY-MM-DD
  - Handles 2-digit years (00-49 → 2000+, 50-99 → 1900+)
  - Returns None for invalid dates

**Data Structure**:
```python
{
    'foa_id': str or None,
    'title': str or None,
    'agency': str or None,
    'open_date': str (ISO 8601) or None,
    'close_date': str (ISO 8601) or None,
    'eligibility': str or None,
    'program_description': str or None,
    'award_range': str or None,
    'source_url': str,
}
```

### 2. SemanticTagger

**Responsibility**: Apply rule-based semantic tags to FOA data

**Key Methods**:
- `tag(foa_data)`: Generate semantic tags
  - Combines title, description, and eligibility text
  - Performs case-insensitive keyword matching
  - Returns deduplicated list of tags

**Tag Categories**:

| Category | Tags | Keywords |
|----------|------|----------|
| Research Domains | AI, Biology, Climate, Physics, Engineering, Health | machine learning, genomics, carbon, quantum, mechanical, disease |
| Methods | Computational, Experimental, Theoretical, Data-Driven | simulation, laboratory, mathematical, analytics |
| Populations | Underrepresented, Students, International | minority, graduate, global |
| Sponsor Themes | Innovation, Collaboration, Education, Infrastructure | novel, partnership, training, facility |

**Tag Format**: `category:value` (e.g., `domain:AI`, `method:Computational`)

### 3. FOAPipeline

**Responsibility**: Orchestrate the full workflow

**Key Methods**:
- `process_url(url)`: Main processing pipeline
  1. Fetch HTML from URL
  2. Detect source and parse
  3. Generate FOA ID if missing
  4. Apply semantic tags
  5. Return complete FOA data

- `export_json(foa_data, output_path)`: Export to JSON
  - Pretty-printed with 2-space indentation
  - Preserves all fields and tags

- `export_csv(foa_data, output_path)`: Export to CSV
  - Flattens semantic_tags to semicolon-separated values
  - Uses pandas for robust CSV handling

## Error Handling

The pipeline gracefully handles errors at each stage:

1. **Network Errors**: Log and return None
2. **Parsing Errors**: Continue with None values for missing fields
3. **Missing Fields**: Use None or empty string as appropriate
4. **Invalid Dates**: Skip date parsing, continue with other fields
5. **File I/O Errors**: Log and raise for user awareness

## Extensibility Points

### Adding a New FOA Source

1. **Create Parser Method**:
```python
def parse_new_agency(self, html: str, url: str) -> Dict:
    soup = BeautifulSoup(html, 'html.parser')
    foa_data = {
        'foa_id': None,
        'title': None,
        # ... extract fields
    }
    return foa_data
```

2. **Update Router**:
```python
if 'new-agency.gov' in url.lower():
    foa_data = self.extractor.parse_new_agency(html, url)
```

### Adding New Semantic Tags

1. **Extend Tag Dictionaries**:
```python
self.research_domains['NewDomain'] = ['keyword1', 'keyword2']
self.methods['NewMethod'] = ['keyword1', 'keyword2']
```

2. **Tags Applied Automatically**: No other changes needed

### Implementing Embedding-Based Tagging

1. **Create New Tagger Class**:
```python
class EmbeddingTagger:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.tag_embeddings = self._create_embeddings()
    
    def tag(self, foa_data: Dict) -> List[str]:
        # Compute similarity and return tags
        pass
```

2. **Swap in Pipeline**:
```python
self.tagger = EmbeddingTagger()  # Instead of SemanticTagger()
```

## Performance Characteristics

- **Single FOA Processing**: ~1-2 seconds (network dependent)
- **Memory Usage**: ~50-100 MB per FOA
- **Scalability**: Linear with number of FOAs (no caching)

## Future Enhancements

1. **Batch Processing**: Process multiple FOAs efficiently
2. **Caching**: Cache parsed FOAs to avoid re-processing
3. **Vector Indexing**: FAISS/Chroma for similarity search
4. **LLM Integration**: Improve tagging accuracy
5. **PDF Support**: Extract text from PDF-based FOAs
6. **Incremental Updates**: Only process new/updated FOAs

## Testing Strategy

1. **Unit Tests**: Test each component independently
2. **Integration Tests**: Test full pipeline with real FOA URLs
3. **Edge Cases**: Handle malformed HTML, missing fields, etc.
4. **Performance Tests**: Measure speed and memory usage

## Code Quality

- **Style**: PEP 8 compliant
- **Documentation**: Comprehensive docstrings
- **Error Handling**: Graceful degradation
- **Logging**: Detailed console output
- **Modularity**: Clear separation of concerns
