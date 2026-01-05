#!/usr/bin/env python3
"""
Check compliance of translation against client requirements.
"""
import csv
import sys
import re

def check_compliance(input_path):
    print(f"Checking {input_path}...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = list(reader)

    issues = []
    
    # Rules
    MAX_LEN = 25
    FORBIDDEN_PUNCT = ['，', '。', '、', '；', ',', '.', ';'] # User specifically mentioned avoiding these
    FORBIDDEN_QUOTES = ['“', '”', '"'] # Should use 「」
    
    total_checked = 0
    
    for row in rows:
        zh = row.get('ZH', '').strip()
        row_id = row.get('ID', '?')
        total_checked += 1
        
        if not zh:
            continue

        # 1. Length Check
        if len(zh) > MAX_LEN:
            issues.append(f"[ID {row_id}] Length Violation: {len(zh)} chars > {MAX_LEN}. Content: {zh}")
            
        # 2. Forbidden Punctuation Check
        found_punct = [p for p in FORBIDDEN_PUNCT if p in zh]
        if found_punct:
            issues.append(f"[ID {row_id}] Forbidden Punctuation found {found_punct}. Content: {zh}")
            
        # 3. Quotes Check
        found_quotes = [q for q in FORBIDDEN_QUOTES if q in zh]
        if found_quotes:
            issues.append(f"[ID {row_id}] Incorrect Quotes found {found_quotes}. Should use 「」. Content: {zh}")
            
        # 4. Trailing Period Check (redundant with forbidden list but good to be specific)
        if zh.endswith(('。', '.', '，', ',')):
             issues.append(f"[ID {row_id}] Trailing Punctuation found. Content: {zh}")

    # Report
    print(f"\nChecked {total_checked} rows.")
    if issues:
        print(f"Found {len(issues)} issues:\n")
        for issue in issues:
            print(issue)
        print("\n❌ FAILED Compliance Check")
    else:
        print("\n✅ PASSED Compliance Check. No formatting issues found.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python check_compliance.py <input_tsv>")
        sys.exit(1)
    
    check_compliance(sys.argv[1])
