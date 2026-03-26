#!/usr/bin/env python3
"""
FOA Ingestion and Semantic Tagging Pipeline
Extracts structured data from Funding Opportunity Announcements and applies semantic tags.
"""

import argparse
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FOAExtractor:
    """Extracts structured data from FOA HTML/text content."""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from URL."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def parse_grants_gov(self, html: str, url: str) -> Dict:
        """Parse Grants.gov FOA page."""
        soup = BeautifulSoup(html, 'html.parser')
        foa_data = {
            'foa_id': None,
            'title': None,
            'agency': None,
            'open_date': None,
            'close_date': None,
            'eligibility': None,
            'program_description': None,
            'award_range': None,
            'source_url': url,
        }

        # Extract title
        title_elem = soup.find('h1') or soup.find('h2')
        if title_elem:
            foa_data['title'] = title_elem.get_text(strip=True)

        # Extract FOA ID from URL or content
        foa_id_match = re.search(r'(?:foa|opportunity)[_-]?id[=:]?\s*([A-Z0-9\-]+)', html, re.IGNORECASE)
        if foa_id_match:
            foa_data['foa_id'] = foa_id_match.group(1)

        # Extract dates
        date_pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
        dates = re.findall(date_pattern, html)
        if dates:
            foa_data['open_date'] = self._format_date(dates[0])
            if len(dates) > 1:
                foa_data['close_date'] = self._format_date(dates[-1])

        # Extract agency
        agency_match = re.search(r'(?:agency|sponsor)[:\s]+([A-Za-z\s&]+?)(?:\n|<|$)', html, re.IGNORECASE)
        if agency_match:
            foa_data['agency'] = agency_match.group(1).strip()

        # Extract award range
        award_match = re.search(r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?', html)
        if award_match:
            foa_data['award_range'] = award_match.group(0)

        # Extract program description (first substantial paragraph)
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 100:
                foa_data['program_description'] = text[:500]
                break

        # Extract eligibility
        eligibility_section = soup.find(string=re.compile(r'eligibility', re.IGNORECASE))
        if eligibility_section:
            parent = eligibility_section.parent
            if parent:
                next_elem = parent.find_next('p') or parent.find_next('div')
                if next_elem:
                    foa_data['eligibility'] = next_elem.get_text(strip=True)[:300]

        return foa_data

    def parse_nsf(self, html: str, url: str) -> Dict:
        """Parse NSF FOA page."""
        soup = BeautifulSoup(html, 'html.parser')
        foa_data = {
            'foa_id': None,
            'title': None,
            'agency': 'National Science Foundation',
            'open_date': None,
            'close_date': None,
            'eligibility': None,
            'program_description': None,
            'award_range': None,
            'source_url': url,
        }

        # Extract title
        title_elem = soup.find('h1')
        if title_elem:
            foa_data['title'] = title_elem.get_text(strip=True)

        # Extract NSF solicitation number
        nsf_match = re.search(r'NSF\s*(\d{2})-\d+', html)
        if nsf_match:
            foa_data['foa_id'] = f"NSF-{nsf_match.group(1)}"

        # Extract dates
        date_pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
        dates = re.findall(date_pattern, html)
        if dates:
            foa_data['open_date'] = self._format_date(dates[0])
            if len(dates) > 1:
                foa_data['close_date'] = self._format_date(dates[-1])

        # Extract award range
        award_match = re.search(r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?', html)
        if award_match:
            foa_data['award_range'] = award_match.group(0)

        # Extract program description
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 100 and 'program' in text.lower():
                foa_data['program_description'] = text[:500]
                break

        return foa_data

    @staticmethod
    def _format_date(date_tuple: Tuple[str, str, str]) -> str:
        """Convert date tuple to ISO format."""
        month, day, year = date_tuple
        year = int(year)
        if year < 100:
            year += 2000 if year < 50 else 1900
        try:
            dt = datetime(year, int(month), int(day))
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            return None


class SemanticTagger:
    """Applies rule-based semantic tags to FOA data."""

    def __init__(self):
        self.research_domains = {
            'AI': ['artificial intelligence', 'machine learning', 'deep learning', 'neural', 'nlp'],
            'Biology': ['biology', 'genomics', 'molecular', 'cellular', 'biomedical'],
            'Climate': ['climate', 'environment', 'sustainability', 'carbon', 'renewable'],
            'Physics': ['physics', 'quantum', 'particle', 'cosmology', 'relativity'],
            'Engineering': ['engineering', 'mechanical', 'electrical', 'civil', 'materials'],
            'Health': ['health', 'medical', 'disease', 'clinical', 'pharmaceutical'],
        }

        self.methods = {
            'Computational': ['simulation', 'modeling', 'algorithm', 'computational', 'software'],
            'Experimental': ['experiment', 'laboratory', 'empirical', 'testing', 'measurement'],
            'Theoretical': ['theory', 'mathematical', 'analytical', 'proof', 'framework'],
            'Data-Driven': ['data', 'analytics', 'mining', 'statistical', 'quantitative'],
        }

        self.populations = {
            'Underrepresented': ['underrepresented', 'minority', 'disadvantaged', 'equity'],
            'Students': ['student', 'graduate', 'undergraduate', 'postdoc', 'early-career'],
            'International': ['international', 'global', 'cross-border', 'collaboration'],
        }

        self.sponsor_themes = {
            'Innovation': ['innovation', 'novel', 'breakthrough', 'cutting-edge'],
            'Collaboration': ['collaboration', 'partnership', 'interdisciplinary', 'team'],
            'Education': ['education', 'training', 'workforce', 'capacity-building'],
            'Infrastructure': ['infrastructure', 'facility', 'resource', 'platform'],
        }

    def tag(self, foa_data: Dict) -> List[str]:
        """Generate semantic tags for FOA."""
        tags = []
        text = ' '.join([
            foa_data.get('title', ''),
            foa_data.get('program_description', ''),
            foa_data.get('eligibility', ''),
        ]).lower()

        # Tag research domains
        for domain, keywords in self.research_domains.items():
            if any(kw in text for kw in keywords):
                tags.append(f"domain:{domain}")

        # Tag methods
        for method, keywords in self.methods.items():
            if any(kw in text for kw in keywords):
                tags.append(f"method:{method}")

        # Tag populations
        for population, keywords in self.populations.items():
            if any(kw in text for kw in keywords):
                tags.append(f"population:{population}")

        # Tag sponsor themes
        for theme, keywords in self.sponsor_themes.items():
            if any(kw in text for kw in keywords):
                tags.append(f"theme:{theme}")

        return list(set(tags)) if tags else ['untagged']


class FOAPipeline:
    """Main pipeline orchestrating extraction and tagging."""

    def __init__(self):
        self.extractor = FOAExtractor()
        self.tagger = SemanticTagger()

    def process_url(self, url: str) -> Optional[Dict]:
        """Process a single FOA URL."""
        logger.info(f"Processing: {url}")

        html = self.extractor.fetch_url(url)
        if not html:
            return None

        # Determine source and parse accordingly
        if 'grants.gov' in url.lower():
            foa_data = self.extractor.parse_grants_gov(html, url)
        elif 'nsf.gov' in url.lower():
            foa_data = self.extractor.parse_nsf(html, url)
        else:
            # Generic parsing
            foa_data = self.extractor.parse_grants_gov(html, url)

        # Generate FOA ID if missing
        if not foa_data['foa_id']:
            foa_data['foa_id'] = f"FOA-{uuid.uuid4().hex[:8].upper()}"

        # Apply semantic tags
        foa_data['semantic_tags'] = self.tagger.tag(foa_data)

        logger.info(f"Extracted FOA: {foa_data['title']}")
        return foa_data

    def export_json(self, foa_data: Dict, output_path: Path) -> None:
        """Export FOA data to JSON."""
        with open(output_path, 'w') as f:
            json.dump(foa_data, f, indent=2)
        logger.info(f"Exported JSON: {output_path}")

    def export_csv(self, foa_data: Dict, output_path: Path) -> None:
        """Export FOA data to CSV."""
        df = pd.DataFrame([foa_data])
        # Flatten semantic_tags for CSV
        df['semantic_tags'] = df['semantic_tags'].apply(lambda x: '; '.join(x) if isinstance(x, list) else x)
        df.to_csv(output_path, index=False)
        logger.info(f"Exported CSV: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='FOA Ingestion and Semantic Tagging Pipeline'
    )
    parser.add_argument(
        '--url',
        required=True,
        help='URL of the FOA to process'
    )
    parser.add_argument(
        '--out_dir',
        default='./out',
        help='Output directory for JSON and CSV files'
    )

    args = parser.parse_args()

    # Create output directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Process FOA
    pipeline = FOAPipeline()
    foa_data = pipeline.process_url(args.url)

    if not foa_data:
        logger.error("Failed to process FOA")
        return 1

    # Export results
    pipeline.export_json(foa_data, out_dir / 'foa.json')
    pipeline.export_csv(foa_data, out_dir / 'foa.csv')

    logger.info("Pipeline completed successfully")
    return 0


if __name__ == '__main__':
    exit(main())
