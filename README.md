# FOA Ingestion and Semantic Tagging

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: PEP 8](https://img.shields.io/badge/code%20style-pep8-orange.svg)](https://pep8.org/)

Automated extraction and semantic tagging of Funding Opportunity Announcements (FOAs) from federal agencies. This tool ingests FOA pages, extracts structured data, and applies rule-based semantic tags to support research discovery and grant matching.

## Motivation

Research teams spend significant time manually discovering, parsing, and categorizing funding opportunities across multiple agency websites. This pipeline automates that process, enabling:

- **Faster discovery**: Automatically ingest FOAs from multiple sources
- **Structured data**: Standardized JSON/CSV format for downstream analysis
- **Semantic understanding**: Rule-based tagging for research domains, methods, populations, and themes
- **Reproducibility**: Deterministic extraction and tagging for consistent results

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Process a single FOA
python main.py --url "https://www.nsf.gov/pubs/2024/nsf24001/nsf24001.jsp" --out_dir ./output

# View results
cat output/foa.json
cat output/foa.csv
```

## Features

- **Multi-source ingestion**: Grants.gov and NSF (extensible for additional sources)
- **Structured extraction**: Automatically extracts FOA ID, title, agency, dates, eligibility, award range
- **Semantic tagging**: Rule-based tags across 4 categories (domains, methods, populations, themes)
- **Dual export**: JSON for structured data, CSV for spreadsheet analysis
- **Robust error handling**: Graceful degradation for malformed or missing data
- **Comprehensive logging**: Detailed console output for debugging and monitoring

## Architecture

```
FOA URL
  ↓
[Fetch] → HTTP GET with error handling
  ↓
[Parse] → Source-specific HTML parsing (Grants.gov, NSF, etc.)
  ↓
[Extract] → Regex + BeautifulSoup field extraction
  ↓
[Normalize] → Standardize dates, amounts, text
  ↓
[Tag] → Rule-based keyword matching
  ↓
[Export] → JSON + CSV output
  ↓
Output: foa.json, foa.csv
```

### Components

**FOAExtractor** - Fetches and parses FOA content
- `fetch_url()`: HTTP retrieval with timeout and error handling
- `parse_grants_gov()`: Grants.gov-specific HTML parsing
- `parse_nsf()`: NSF-specific HTML parsing
- `_format_date()`: ISO 8601 date normalization

**SemanticTagger** - Applies rule-based semantic tags
- Keyword matching across 4 tag categories
- Extensible tag dictionaries for easy customization
- Returns deduplicated tag list

**FOAPipeline** - Orchestrates the full workflow
- URL routing to appropriate parser
- Data extraction and tagging
- JSON and CSV export

## Installation

### Requirements
- Python 3.8+
- pip

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/foa-ingestion.git
cd foa-ingestion

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Command

```bash
python main.py --url "<FOA_URL>" --out_dir ./output
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--url` | Yes | - | URL of the FOA page to process |
| `--out_dir` | No | `./out` | Output directory for JSON and CSV files |

### Examples

**NSF FOA:**
```bash
python main.py --url "https://www.nsf.gov/pubs/2024/nsf24001/nsf24001.jsp" --out_dir ./nsf_output
```

**Grants.gov FOA:**
```bash
python main.py --url "https://www.grants.gov/search-results-detail/..." --out_dir ./grants_output
```

## Output Schema

### JSON Format

```json
{
  "foa_id": "NSF-24-001",
  "title": "Artificial Intelligence Research Institutes",
  "agency": "National Science Foundation",
  "open_date": "2024-01-15",
  "close_date": "2024-06-30",
  "eligibility": "Eligible organizations include institutions of higher education...",
  "program_description": "The AI Institutes program aims to establish a network...",
  "award_range": "$20,000,000 - $25,000,000",
  "source_url": "https://www.nsf.gov/pubs/2024/nsf24001/nsf24001.jsp",
  "semantic_tags": [
    "domain:AI",
    "method:Computational",
    "theme:Collaboration",
    "theme:Education",
    "population:Students"
  ]
}
```

### CSV Format

Same fields as JSON, with `semantic_tags` as semicolon-separated values.

## Semantic Tags

Tags are organized by category:

| Category | Values |
|----------|--------|
| **Research Domains** | AI, Biology, Climate, Physics, Engineering, Health |
| **Methods** | Computational, Experimental, Theoretical, Data-Driven |
| **Populations** | Underrepresented, Students, International |
| **Sponsor Themes** | Innovation, Collaboration, Education, Infrastructure |

## Extending the Pipeline

### Adding a New FOA Source

1. Add a parsing method to `FOAExtractor`:

```python
def parse_new_agency(self, html: str, url: str) -> Dict:
    """Parse FOA from new agency."""
    soup = BeautifulSoup(html, 'html.parser')
    foa_data = {
        'foa_id': None,
        'title': None,
        'agency': 'Agency Name',
        # ... extract fields
    }
    return foa_data
```

2. Update `FOAPipeline.process_url()` to detect and route:

```python
if 'new-agency.gov' in url.lower():
    foa_data = self.extractor.parse_new_agency(html, url)
```

### Adding New Semantic Tags

Extend the tag dictionaries in `SemanticTagger.__init__()`:

```python
self.research_domains['NewDomain'] = ['keyword1', 'keyword2', ...]
self.methods['NewMethod'] = ['keyword1', 'keyword2', ...]
```

Tags are automatically applied during processing.

## Sample Output

See `sample_output/` directory for example JSON and CSV outputs.

## Testing

```bash
# Test with NSF FOA
python main.py --url "https://www.nsf.gov/pubs/2024/nsf24001/nsf24001.jsp" --out_dir ./test

# Verify JSON is valid
python -m json.tool test/foa.json

# Check CSV format
head -2 test/foa.csv
```

## Logging

The script outputs detailed logs to console:

```
2024-01-15 10:30:45 - __main__ - INFO - Processing: https://...
2024-01-15 10:30:46 - __main__ - INFO - Extracted FOA: Funding Opportunity Title
2024-01-15 10:30:46 - __main__ - INFO - Exported JSON: ./output/foa.json
2024-01-15 10:30:46 - __main__ - INFO - Exported CSV: ./output/foa.csv
```

## Future Improvements

- **Embedding-based tagging**: Use sentence-transformers for semantic similarity
- **LLM-assisted classification**: Improve tagging accuracy for complex FOAs
- **Vector indexing**: FAISS/Chroma for similarity search
- **PDF support**: Extract text from PDF-based FOAs
- **Batch processing**: Process multiple FOAs efficiently
- **Additional sources**: NIH, USDA, DOE, and other agencies
- **Web interface**: Simple UI for browsing and searching FOAs

## Architecture Diagram

See `architecture/` directory for detailed pipeline diagrams and component descriptions.

## Contributing

Contributions welcome! Please:
1. Follow PEP 8 style guidelines
2. Add docstrings to all functions
3. Include error handling
4. Test with real FOA URLs

## Example Run

```bash
python main.py --url "https://www.nsf.gov/pubs/2024/nsf24001/nsf24001.jsp" --out_dir ./output
```

**Terminal Output:**
```
INFO - Processing: https://www.nsf.gov/...
INFO - Extracted FOA: Artificial Intelligence Research Institutes
INFO - Exported JSON: ./output/foa.json
INFO - Exported CSV: ./output/foa.csv
```

## GSoC 2026

This project is part of Google Summer of Code 2026 with the HumanAI Organization.

## Contact

For questions or issues, open a GitHub issue or contact the HumanAI team at human-ai@cern.ch
