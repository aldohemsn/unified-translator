import csv

file_path = "sample/tongwei_solar.tsv"
locked_count = 0
target_rows = ['2', '8']
rows_data = {}

with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for row in reader:
        # Check explicit LOCKED column
        is_locked = row.get('LOCKED', '0').strip() == '1'
        if is_locked:
            locked_count += 1
            
        if row.get('ID') in target_rows:
            rows_data[row.get('ID')] = row

print(f"Total LOCKED rows found: {locked_count}")
for rid in target_rows:
    if rid in rows_data:
        print(f"Row {rid}: {rows_data[rid]}")
    else:
        print(f"Row {rid} not found.")
