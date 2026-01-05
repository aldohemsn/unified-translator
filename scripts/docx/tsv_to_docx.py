#!/usr/bin/env python3
"""
Convert proofread TSV back to DOCX format for the "They Shall Not Grow Old" translation
"""
import docx
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import csv
import sys
from datetime import datetime

def create_proofread_docx(tsv_path, output_path, original_docx=None):
    """
    Create a new DOCX with proofread translations
    
    Args:
        tsv_path: Path to the proofread TSV file
        output_path: Path to save the output DOCX
        original_docx: Optional path to original DOCX to match styling
    """
    
    # Read TSV data
    with open(tsv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = list(reader)
    
    # Create document
    doc = Document()
    
    # Add title
    title = doc.add_heading('They Shall Not Grow Old (2018)', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Add metadata
    metadata = doc.add_paragraph()
    metadata.add_run(f'Proofread on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n').italic = True
    metadata.add_run(f'Total segments: {len(rows)}\n').italic = True
    metadata.add_run('Video Translation Strategy: Context-Aware Subtitling with Transcription Audit\n').italic = True
    metadata.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph()  # Spacing
    
    # Create table
    table = doc.add_table(rows=1, cols=5)
    table.style = 'Light Grid Accent 1'
    
    # Header row
    header_cells = table.rows[0].cells
    headers = ['ID', '#', 'Source (EN)', 'Match', 'Target (ZH) - Proofread']
    for i, header in enumerate(headers):
        cell = header_cells[i]
        cell.text = header
        # Bold header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
    
    # Data rows
    for row_data in rows:
        row_cells = table.add_row().cells
        row_cells[0].text = ''  # Empty first column (messy ID)
        row_cells[1].text = row_data.get('ID', '')  # Clean ID
        row_cells[2].text = row_data.get('Source', '')  # English source
        row_cells[3].text = ''  # Match column (empty)
        row_cells[4].text = row_data.get('Target', '')  # Proofread Chinese
        
        # Add comment if exists
        comment = row_data.get('Comments', '').strip()
        if comment:
            # Check for transcription flags
            if '[TRANSCRIPTION FLAG]' in comment:
                # Highlight in yellow
                for paragraph in row_cells[2].paragraphs:
                    for run in paragraph.runs:
                        run.font.highlight_color = 7  # Yellow
            
            # Add comment as footnote in target cell
            comment_para = row_cells[4].add_paragraph()
            comment_run = comment_para.add_run(f'\n[Note: {comment}]')
            comment_run.font.size = Pt(8)
            comment_run.font.color.rgb = RGBColor(128, 128, 128)
            comment_run.italic = True
    
    # Set column widths
    for row in table.rows:
        row.cells[0].width = Inches(0.3)  # ID messy
        row.cells[1].width = Inches(0.4)  # ID clean
        row.cells[2].width = Inches(2.5)  # English
        row.cells[3].width = Inches(0.5)  # Match
        row.cells[4].width = Inches(2.5)  # Chinese
    
    # Save document
    doc.save(output_path)
    print(f"✓ Created proofread DOCX: {output_path}")
    print(f"  Total rows processed: {len(rows)}")
    
    # Count transcription flags
    transcription_flags = sum(1 for r in rows if '[TRANSCRIPTION FLAG]' in r.get('Comments', ''))
    if transcription_flags > 0:
        print(f"  ⚠️  Found {transcription_flags} transcription issues (highlighted in yellow)")
    
    return len(rows)

def generate_proofreading_summary(tsv_path, output_txt):
    """Generate a summary report of the proofreading"""
    
    with open(tsv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = list(reader)
    
    transcription_issues = []
    vo_os_breakdown = {'VO': 0, 'OS': 0, 'Unknown': 0}
    
    for row in rows:
        comment = row.get('Comments', '')
        
        # Check for transcription flags
        if '[TRANSCRIPTION FLAG]' in comment:
            transcription_issues.append({
                'id': row.get('ID'),
                'source': row.get('Source'),
                'comment': comment
            })
        
        # Count VO/OS
        if comment.startswith('VO'):
            vo_os_breakdown['VO'] += 1
        elif comment.startswith('OS'):
            vo_os_breakdown['OS'] += 1
        else:
            vo_os_breakdown['Unknown'] += 1
    
    # Write summary
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("PROOFREADING SUMMARY REPORT\n")
        f.write("They Shall Not Grow Old (2018)\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Strategy: Video Translation (Context-Aware Subtitling)\n\n")
        
        f.write("-" * 70 + "\n")
        f.write("STATISTICS\n")
        f.write("-" * 70 + "\n")
        f.write(f"Total Segments: {len(rows)}\n")
        f.write(f"Voice-Over (VO): {vo_os_breakdown['VO']} segments\n")
        f.write(f"On-Screen (OS): {vo_os_breakdown['OS']} segments\n")
        f.write(f"Transcription Issues Found: {len(transcription_issues)}\n\n")
        
        if transcription_issues:
            f.write("-" * 70 + "\n")
            f.write("TRANSCRIPTION ISSUES DETECTED\n")
            f.write("-" * 70 + "\n\n")
            for issue in transcription_issues:
                f.write(f"ID {issue['id']}:\n")
                f.write(f"  Source: {issue['source']}\n")
                f.write(f"  Issue: {issue['comment']}\n\n")
        
        f.write("-" * 70 + "\n")
        f.write("SAMPLE IMPROVEMENTS (First 5)\n")
        f.write("-" * 70 + "\n\n")
        for i, row in enumerate(rows[:5], 1):
            f.write(f"{i}. ID {row.get('ID')}\n")
            f.write(f"   EN: {row.get('Source')}\n")
            f.write(f"   ZH: {row.get('Target')}\n")
            if row.get('Comments'):
                f.write(f"   Note: {row.get('Comments')}\n")
            f.write("\n")
        
        f.write("-" * 70 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 70 + "\n")
    
    print(f"✓ Created summary report: {output_txt}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python tsv_to_docx.py <proofread_tsv> <output_docx> [summary_txt]")
        sys.exit(1)
    
    tsv_path = sys.argv[1]
    output_docx = sys.argv[2]
    summary_txt = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Create DOCX
    create_proofread_docx(tsv_path, output_docx)
    
    # Generate summary if requested
    if summary_txt:
        generate_proofreading_summary(tsv_path, summary_txt)
