import csv
import logging

# Setup mock data
rows = []
file_path = "sample/tongwei_solar.tsv"
with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for row in reader:
        # Normalize keys as per TSVHandler logic simulation
        src = row.get('Source') or row.get('EN') or row.get('English') or ''
        rows.append({'Source': src})

print(f"Loaded {len(rows)} rows.")

# Simulate raw_segments (e.g., LLM returns small chunks of ~3-5 lines)
raw_segments = []
chunk_size = 3
for i in range(0, len(rows), chunk_size):
    end = min(i + chunk_size - 1, len(rows) - 1)
    raw_segments.append({'start': i, 'end': end})

print(f"Simulated {len(raw_segments)} raw segments (naive chunking of {chunk_size}).")

# --- Merging Logic (Copied from LegalStrategy) ---
merged_segments = []
            
# Configuration for merging
TARGET_CHARS = 1500      # Aim for ~1500 chars per batch
MAX_LINES_PER_BATCH = 40 # Hard limit

if not raw_segments:
    print("No segments.")
    exit()

def get_segment_text_len(seg_start, seg_end):
    """Calculate total character length of a segment range."""
    length = 0
    for i in range(seg_start, seg_end + 1):
        if i < len(rows):
            length += len(rows[i].get('Source', ''))
    return length

current_seg = raw_segments[0]
current_char_count = get_segment_text_len(current_seg['start'], current_seg['end'])

for next_seg in raw_segments[1:]:
    next_char_count = get_segment_text_len(next_seg['start'], next_seg['end'])
    
    current_lines = current_seg['end'] - current_seg['start'] + 1
    next_lines = next_seg['end'] - next_seg['start'] + 1
    total_lines = current_lines + next_lines
    total_chars = current_char_count + next_char_count
    
    should_merge = False
    
    if total_lines <= MAX_LINES_PER_BATCH:
        if current_char_count < TARGET_CHARS:
            should_merge = True
        elif next_char_count < 100: # Always gobble up tiny stragglers
            should_merge = True
    
    if should_merge:
        # Merge next into current
        current_seg['end'] = next_seg['end']
        current_char_count = total_chars
    else:
        # Finalize current and move to next
        merged_segments.append(current_seg)
        current_seg = next_seg
        current_char_count = next_char_count

# Append the last segment
merged_segments.append(current_seg)

# --- Analysis ---
print(f"Merged into {len(merged_segments)} segments.")

seg_lines = []
seg_chars = []

for seg in merged_segments:
    lines = seg['end'] - seg['start'] + 1
    chars = get_segment_text_len(seg['start'], seg['end'])
    seg_lines.append(lines)
    seg_chars.append(chars)

import statistics
if seg_lines:
    print(f"Avg Lines per Batch: {statistics.mean(seg_lines):.2f}")
    print(f"Max Lines per Batch: {max(seg_lines)}")
    print(f"Min Lines per Batch: {min(seg_lines)}")
    print(f"Avg Chars per Batch: {statistics.mean(seg_chars):.2f}")
    print(f"Max Chars per Batch: {max(seg_chars)}")
