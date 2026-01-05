#!/usr/bin/env python3
"""
Apply client strict formatting rules to the proofread TSV.
Rules based on 'unified-translator/sample/项目客户要求.txt':
1. No commas (，), periods (。), semicolons (；), enumerated commas (、). Replace with space.
2. End of line punctuation: remove periods.
3. Quotes: Use 「」 instead of “”.
4. OS Text: Prefix with @.
"""
import csv
import sys
import re

def apply_formatting(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        fieldnames = reader.fieldnames
        rows = list(reader)

    formatted_rows = []
    
    for row in rows:
        target = row.get('Target', '')
        comment = row.get('Comments', '')
        
        if not target:
            formatted_rows.append(row)
            continue
            
        # 1. Quotes Conversion: “” -> 「」
        # Simple replacement might be risky if nesting exists, but usually okay for subtitles
        target = target.replace('“', '「').replace('”', '」')
        target = target.replace('"', '「') # simplistic assumption for English quotes left over
        
        # 2. End of line cleanup
        # Remove trailing period
        if target.strip().endswith('。'):
            target = target.strip()[:-1]
            
        # 3. Middle punctuation replacement -> Space
        # Forbidden: 、 ， ； 。 ～ ——
        # Allow: ！ ？ … 「 」 （ ） · 《 》
        
        # Replace forbidden distinct marks with space
        chars_to_space = ['，', '、', '；', '。', ',', ';'] # converting English ones too just in case
        for char in chars_to_space:
            target = target.replace(char, ' ')
            
        # Remove -- or —— completely or space? Rule says "不得使用--符号", likely meant replace with ... or nothing. 
        # But for strictly separating pauses, space is safer.
        target = target.replace('——', ' ')
        
        # 4. Collapse multiple spaces to single space
        target = re.sub(r'\s+', ' ', target)
        
        # 5. OS Formatting
        # If comment indicates OS, prepend @
        # Detect OS from Comments column (e.g., "OS (On-Screen Text)...")
        if re.search(r'\bOS\b', comment) or 'On-Screen' in comment:
            # Check if not already prefixed
            if not target.startswith('@'):
                target = f"@{target}"
        
        row['Target'] = target.strip()
        formatted_rows.append(row)
        
    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        writer.writerows(formatted_rows)
        
    print(f"✓ Applied formatting to {len(formatted_rows)} rows.")
    print(f"  Saved to {output_path}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python apply_client_format.py <input_tsv> <output_tsv>")
        sys.exit(1)
        
    apply_formatting(sys.argv[1], sys.argv[2])
