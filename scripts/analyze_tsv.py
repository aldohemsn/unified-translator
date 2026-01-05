import csv
import statistics

file_path = "sample/tongwei_solar.tsv"

lengths = []
empty_rows = 0
short_rows = 0 # < 20 chars
long_rows = 0 # > 100 chars
total_rows = 0

with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for row in reader:
        # Manually handle alias for this script
        source = row.get('Source') or row.get('EN') or row.get('English') or ''
        source = source.strip()
        
        total_rows += 1
        length = len(source)
        lengths.append(length)
        
        if length == 0:
            empty_rows += 1
        elif length < 20:
            short_rows += 1
        elif length > 100:
            long_rows += 1

avg_len = statistics.mean(lengths) if lengths else 0
median_len = statistics.median(lengths) if lengths else 0

print(f"Total Rows: {total_rows}")
print(f"Avg Length: {avg_len:.2f} chars")
print(f"Median Length: {median_len} chars")
print(f"Empty Rows: {empty_rows} ({empty_rows/total_rows:.1%})")
print(f"Short Rows (<20 chars): {short_rows} ({short_rows/total_rows:.1%})")
print(f"Long Rows (>100 chars): {long_rows} ({long_rows/total_rows:.1%})")

print("\n--- Sample Consecutive Rows ---")
with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    rows = list(reader)
    for i in range(min(20, len(rows))):
        src = rows[i].get('Source') or rows[i].get('EN') or ''
        print(f"Row {i}: {src[:50]}...")