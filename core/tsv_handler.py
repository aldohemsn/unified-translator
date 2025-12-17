import csv
import logging
import os
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class TSVHandler:
    def __init__(self):
        # Define aliases
        self.aliases = {
            'ID': ['id', '#', 'no.', 'index', 'key'],
            'Source': ['english', 'source', 'en', 'src', 'original'],
            'Target': ['chinese', 'target', 'zh', 'tgt', 'translation', 'cn']
        }

    def _normalize_header(self, headers: List[str]) -> Tuple[List[str], Dict[str, str]]:
        """
        Identify mapping from actual header to standardized header (ID, Source, Target).
        Returns: (Normalized Headers List, Mapping Dict)
        """
        mapping = {}
        normalized_headers = []
        
        lower_headers = [h.lower().strip() for h in headers]
        
        # Try to find columns
        def find_index(possible_names):
            for i, h in enumerate(lower_headers):
                if any(alias == h for alias in possible_names):
                    return i
                if any(alias in h for alias in possible_names): # Partial match
                    return i
            return -1

        id_idx = find_index(self.aliases['ID'])
        src_idx = find_index(self.aliases['Source'])
        tgt_idx = find_index(self.aliases['Target'])

        # Check if we found required columns (ID and Source)
        if id_idx == -1 or src_idx == -1:
            # Fallback for files without standard headers
            if len(headers) >= 3:
                logger.warning("Standard headers not found. Falling back to positional mapping: Col 1=ID, 2=Source, 3=Target")
                id_idx, src_idx, tgt_idx = 0, 1, 2
            elif len(headers) == 2:
                logger.warning("Standard headers not found. Falling back to positional mapping: Col 1=ID, 2=Source")
                id_idx, src_idx = 0, 1
                tgt_idx = -1
            else:
                 raise ValueError(f"Could not identify required columns (ID, Source) in headers: {headers}")

        # Construct mapping
        original_to_standard = {}
        
        # We want to preserve other columns too, but map the key ones
        for i, h in enumerate(headers):
            if i == id_idx:
                normalized_headers.append('ID')
                original_to_standard[h] = 'ID'
            elif i == src_idx:
                normalized_headers.append('Source')
                original_to_standard[h] = 'Source'
            elif i == tgt_idx:
                normalized_headers.append('Target')
                original_to_standard[h] = 'Target'
            else:
                normalized_headers.append(h) # Keep others as is
                original_to_standard[h] = h
                
        return normalized_headers, original_to_standard

    def read_file(self, path: str) -> List[Dict[str, str]]:
        """
        Read TSV file and return list of dicts with standardized keys (ID, Source, Target).
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        data = []
        with open(path, 'r', encoding='utf-8') as f:
            # Read first line to check headers
            first_line = f.readline()
            if not first_line:
                return []
            
            f.seek(0)
            
            # Use csv reader
            reader = csv.reader(f, delimiter='\t')
            headers = next(reader, None)
            
            if not headers:
                return []

            # Normalize headers
            norm_headers, mapping = self._normalize_header(headers)
            
            # Map column indices to standardized names
            # We need to know which index maps to which standard name
            # Let's rebuild the map based on indices
            
            index_map = {}
            # We need to run finding logic again on the actual header row
            # Or simpler: just use DictReader with the *original* headers, and then re-map keys
            
        # Re-open for DictReader
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            # Verify we can map the fieldnames
            if not reader.fieldnames:
                 return []
            
            _, mapping = self._normalize_header(reader.fieldnames)
            
            for row in reader:
                new_row = {}
                for k, v in row.items():
                    if k in mapping:
                        new_row[mapping[k]] = v
                    else:
                        new_row[k] = v # Keep extra columns
                
                # Ensure Target column exists
                if 'Target' not in new_row:
                    new_row['Target'] = ''
                
                # Filter empty rows (where Source or Target is empty)
                # Also keep LOCKED rows even if empty
                if new_row.get('Source') or new_row.get('Target') or new_row.get('LOCKED') == '1':
                    data.append(new_row)
                    
        return data

    def write_file(self, path: str, data: List[Dict[str, str]], override_headers: Optional[List[str]] = None):
        """
        Write data to TSV. 
        Ensures ID, Source, Target are first.
        """
        if not data:
            logger.warning("No data to write.")
            return

        # Determine headers
        if override_headers:
            fieldnames = override_headers
        else:
            # Default order
            keys = list(data[0].keys())
            priority = ['ID', 'Source', 'Target']
            fieldnames = [k for k in priority if k in keys] + [k for k in keys if k not in priority]

        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            writer.writerows(data)
