import csv
import re
import sys

def load_glossary(path):
    glossary = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                if 'EN_TERM' in row and 'ZH_TERM' in row:
                    glossary[row['EN_TERM'].strip()] = row['ZH_TERM'].strip()
    except Exception as e:
        print(f"Error loading glossary: {e}")
    return glossary

def is_chinese_char(char):
    return '\u4e00' <= char <= '\u9fff'

def audit_translation(input_path, glossary_path):
    print(f"Auditing {input_path} against {glossary_path}...\n")
    
    glossary = load_glossary(glossary_path)
    issues = []
    
    # Common Legal QA Rules
    common_errors = {
        r'\bshall\b': {'expect': ['应', '须'], 'incorrect': ['将', '会', '要'], 'msg': "Legal 'shall' usually translates to '应' or '须'."},
        r'\bmay\b': {'expect': ['可', '有权'], 'incorrect': [], 'msg': "Legal 'may' usually translates to '可'."},
        r'\bParty\b': {'expect': ['方'], 'incorrect': ['党'], 'msg': "'Party' in contract usually means '方', not '党'."},
        r'\bParties\b': {'expect': ['双方', '各方'], 'incorrect': [], 'msg': "'Parties' usually means '双方' or '各方'."},
    }

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            rows = list(reader)
            
            for i, row in enumerate(rows):
                line_num = i + 2 # Header is line 1
                rid = row.get('ID', str(line_num))
                source = row.get('Source', '').strip()
                target = row.get('Target', '').strip()
                is_locked = row.get('LOCKED', '0') == '1'
                
                # Skip merged lines placeholders or empty lines
                if target in ["[[MERGED_UP]]", "[[MERGED_DOWN]]", "[[LOCKED]]", "[[MISSING_TRANSLATION]]"]:
                    continue
                if not source or not target:
                    continue
                
                # 1. Glossary Check
                for en_term, zh_term in glossary.items():
                    # Simple case-insensitive check
                    if re.search(r'\b' + re.escape(en_term) + r'\b', source, re.IGNORECASE):
                        # Split zh_term by / for options
                        options = [opt.strip() for opt in zh_term.split('/')]
                        if not any(opt in target for opt in options):
                            # Double check: sometimes term is kept in English
                            if en_term not in target:
                                issues.append({
                                    'line': line_num, 'id': rid, 'type': 'Glossary',
                                    'msg': f"Missing term '{zh_term}' for source '{en_term}'"
                                })

                # 2. Number Consistency
                # Extract numbers from source and target
                src_nums = re.findall(r'\d+(?:\.\d+)?', source)
                tgt_nums = re.findall(r'\d+(?:\.\d+)?', target)
                
                # Filter out numbers that might be part of words or dates if format differs, 
                # but simple set comparison is a good heuristic
                if set(src_nums) != set(tgt_nums):
                    # Ignore strict equality for now, just check if source nums are present in target
                    # (Target might have more numbers due to formatting, e.g. "one (1)")
                    missing_nums = [n for n in src_nums if n not in tgt_nums]
                    if missing_nums:
                         issues.append({
                            'line': line_num, 'id': rid, 'type': 'Numbers',
                            'msg': f"Potential missing numbers: {missing_nums}"
                        })

                # 3. Punctuation (English comma in Chinese text)
                # Check if target has English comma followed by Chinese char, or vice versa
                if ',' in target:
                    # Heuristic: if sentence is mostly Chinese but has English comma
                    cn_chars = sum(1 for c in target if is_chinese_char(c))
                    if cn_chars > len(target) / 2:
                        issues.append({
                            'line': line_num, 'id': rid, 'type': 'Punctuation',
                            'msg': "Found English comma (,) in Chinese text. Should likely be '，' or '、'."
                        })
                
                # 4. Extra Spaces in Chinese
                if re.search(r'[\u4e00-\u9fff]\s+[\u4e00-\u9fff]', target):
                     # Exception: sometimes spaces are used for formatting in lists, but in sentences they are rare
                     issues.append({
                        'line': line_num, 'id': rid, 'type': 'Format',
                        'msg': "Unexpected space between Chinese characters."
                    })

                # 5. Legal Terms QA
                for pattern, rule in common_errors.items():
                    if re.search(pattern, source, re.IGNORECASE):
                        if rule['incorrect']:
                            for wrong in rule['incorrect']:
                                if wrong in target:
                                    issues.append({
                                        'line': line_num, 'id': rid, 'type': 'Legal Term',
                                        'msg': f"Found suspicious translation '{wrong}' for '{pattern}'. {rule['msg']}"
                                    })
                        # Check expected (optional, as there might be synonyms)
                        # if rule['expect'] and not any(exp in target for exp in rule['expect']):
                        #    pass 

                # 6. Untranslated English (High ratio of EN chars in Target)
                if len(target) > 5:
                    en_chars_in_tgt = len(re.findall(r'[a-zA-Z]', target))
                    if en_chars_in_tgt > len(target) * 0.8: # >80% English
                         issues.append({
                            'line': line_num, 'id': rid, 'type': 'Untranslated',
                            'msg': "Target appears to be mostly English."
                        })

    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Print Report
    if not issues:
        print("No obvious issues found!")
    else:
        print(f"Found {len(issues)} potential issues:\n")
        print(f"{ 'Line':<6} | { 'ID':<6} | { 'Type':<12} | {'Message'}")
        print("-" * 80)
        for issue in issues[:50]: # Limit output to 50 items to avoid flooding
            print(f"{issue['line']:<6} | {issue['id']:<6} | {issue['type']:<12} | {issue['msg']}")
        
        if len(issues) > 50:
            print(f"\n... and {len(issues) - 50} more issues.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python audit_translation.py <input_tsv> <glossary_tsv>")
    else:
        audit_translation(sys.argv[1], sys.argv[2])
