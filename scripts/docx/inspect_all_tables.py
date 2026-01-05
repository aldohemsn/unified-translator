import docx
import sys

def inspect_all_tables(file_path):
    try:
        doc = docx.Document(file_path)
        print(f"Total Tables: {len(doc.tables)}")
        
        for i, table in enumerate(doc.tables):
            print(f"\n--- Table {i+1} ---")
            # Print the first 3 rows of each table to identify structure
            for j, row in enumerate(table.rows[:3]):
                cells = [cell.text.strip().replace('\n', ' ')[:30] for cell in row.cells]
                print(f"Row {j}: {cells}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_all_tables.py <file_path>")
    else:
        inspect_all_tables(sys.argv[1])

