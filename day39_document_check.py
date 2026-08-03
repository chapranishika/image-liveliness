"""
day39_document_check.py

Phase C: Documentation Consistency Check (Day 39)
Scans documentation files (markdown, docx, and pdf) to locate and report stale claims
regarding "synthetic impostor" score distributions or placeholders. 

DELIBERATE DESIGN DECISION:
This script explicitly refuses to modify any files automatically. Security evaluation
reports and architectural summaries must be reviewed and corrected by a human to preserve
absolute integrity and accuracy.
"""
import os
import sys
import re
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader

# List of designated documentation paths
DOCUMENT_PATHS = [
    os.path.abspath("README.md"),
    os.path.abspath("data/Evaluation_Report.md"),
    os.path.abspath("Full_Approach_Design_Document_v2.docx"),
    os.path.abspath("docs/Secure_Face_Framework_Calibration_Report.pdf"),
    os.path.abspath(r"C:\Users\chapr\.gemini\antigravity\brain\cdb6da55-eccf-4c19-a755-1b04570913ff\walkthrough.md")
]

# Patterns designed to capture stale phrasings and placeholders
PATTERNS = [
    r"synthetic.{0,50}impostor",
    r"impostor.{0,50}synthetic",
    r"placeholder.{0,50}impostor",
    r"impostor.{0,50}placeholder",
    r"impostor.{0,50}distribution.{0,30}synthetic"
]

def extract_text_from_docx(filepath):
    """Parses Word document XML natively to extract plain text."""
    try:
        with zipfile.ZipFile(filepath) as docx:
            xml_content = docx.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                text_nodes = p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
                p_text = "".join(node.text for node in text_nodes if node.text)
                if p_text:
                    paragraphs.append(p_text)
            return "\n".join(paragraphs)
    except Exception as e:
        return f"[Error docx extraction: {e}]"

def extract_text_from_pdf(filepath):
    """Uses pypdf to extract plain text from PDF file."""
    try:
        reader = PdfReader(filepath)
        text_pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
        return "\n".join(text_pages)
    except Exception as e:
        return f"[Error pdf extraction: {e}]"

def extract_text(filepath):
    """Reads plain text based on file format extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in [".md", ".txt"]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext == ".docx":
        return extract_text_from_docx(filepath)
    elif ext == ".pdf":
        return extract_text_from_pdf(filepath)
    else:
        return ""

def main():
    print("=" * 90)
    print("DAY 39 — SYSTEM DOCUMENTATION CONSISTENCY CHECK")
    print("Searching for stale synthetic impostor claims across designated files.")
    print("=" * 90)

    compiled_regexes = [re.compile(pat, re.IGNORECASE) for pat in PATTERNS]
    stale_count = 0
    checked_files = 0

    for path in DOCUMENT_PATHS:
        if not os.path.exists(path):
            print(f"[SKIP] File not found: {path}")
            continue

        print(f"\n[AUDIT] Scanning {os.path.basename(path)} ...")
        checked_files += 1
        text = extract_text(path)
        
        # Search line by line to show context (useful for manual corrections)
        lines = text.split("\n")
        file_stale_count = 0
        
        for line_num, line in enumerate(lines, 1):
            for regex in compiled_regexes:
                match = regex.search(line)
                if match:
                    # Report occurrence with context
                    print(f"  --> FOUND Line {line_num} | Pattern: '{regex.pattern}'")
                    print(f"      Context: \"... {line.strip()[:100]} ...\"")
                    file_stale_count += 1
                    stale_count += 1
                    
        if file_stale_count == 0:
            print("  --> [OK] No stale synthetic claims detected.")
            
    print("\n" + "=" * 90)
    print("CONSISTENCY CHECK AUDIT SUMMARY")
    print("=" * 90)
    print(f"Files successfully scanned: {checked_files}")
    print(f"Stale placeholder references located: {stale_count}")
    print("=" * 90)

    print("\nIMPORTANT HUMAN OPERATOR INSTRUCTIONS:")
    print("  1. This tool NEVER modifies documents automatically to prevent trust issues.")
    print("  2. If any stale claims were found, manually open and rewrite those sections.")
    print("  3. LIMITATION: Automated filters can miss text hidden in tables or charts.")
    print("  4. Regardless of this script's outcome, you MUST manually review and read")
    print("     docs/Secure_Face_Framework_Calibration_Report.pdf and data/Evaluation_Report.md")
    print("     one final time before calling consistency checks complete.")
    
    if stale_count > 0:
        sys.exit(1)
    else:
        print("\n🎉 Consistency check passed! All automated document patterns are clean.")
        sys.exit(0)

if __name__ == "__main__":
    main()
