import docx
import sys

def inspect_docx(file_path):
    try:
        doc = docx.Document(file_path)
        print(f"Total Paragraphs: {len(doc.paragraphs)}")
        print(f"Total Tables: {len(doc.tables)}")
        
        print("\n--- First 20 Paragraphs ---")
        for i, para in enumerate(doc.paragraphs[:20]):
            print(f"[{i}] {para.text[:100]}") # Print first 100 chars
            
        if doc.tables:
            print("\n--- First Table (first 5 rows) ---")
            table = doc.tables[0]
            for i, row in enumerate(table.rows[:5]):
                cells = [cell.text.strip()[:50] for cell in row.cells]
                print(f"Row {i}: {cells}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_docx.py <file_path>")
    else:
        inspect_docx(sys.argv[1])

