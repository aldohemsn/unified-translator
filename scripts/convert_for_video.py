#!/usr/bin/env python3
"""
Convert extracted TSV (ID, EN, ZH, LOCKED) to video strategy format (ID, Source, Target)
"""
import csv
import sys

def convert_tsv(input_path, output_path):
    """Convert from (ID, EN, ZH, LOCKED) to (ID, Source, Target)"""
    with open(input_path, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in, delimiter='\t')
        rows = list(reader)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=['ID', 'Source', 'Target'], delimiter='\t')
        writer.writeheader()
        
        for row in rows:
            writer.writerow({
                'ID': row['ID'],
                'Source': row['EN'],
                'Target': row['ZH']
            })
    
    print(f"✓ Converted {len(rows)} rows from {input_path} to {output_path}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python convert_for_video.py <input_tsv> <output_tsv>")
        sys.exit(1)
    
    convert_tsv(sys.argv[1], sys.argv[2])
