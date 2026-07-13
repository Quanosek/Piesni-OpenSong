#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive analysis of OpenSong Polish hymn files."""

import os
import re
import sys
from collections import defaultdict
from xml.etree import ElementTree as ET

BASE = "/home/runner/work/Piesni-OpenSong/Piesni-OpenSong"

def get_all_files():
    files = []
    for dirpath, dirnames, filenames in os.walk(BASE):
        dirnames[:] = [d for d in dirnames if d != '.git']
        for fn in filenames:
            if fn == 'LICENSE' or fn.endswith('.py') or fn.endswith('.md'):
                continue
            files.append(os.path.join(dirpath, fn))
    return sorted(files)

def parse_song(filepath):
    """Parse an OpenSong XML file, return dict of fields."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, str(e)
    
    # Extract fields using regex (files may have minor XML quirks)
    def extract_tag(tag, text):
        m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', text, re.DOTALL)
        return m.group(1).strip() if m else ''
    
    title = extract_tag('title', content)
    lyrics = extract_tag('lyrics', content)
    presentation = extract_tag('presentation', content)
    author = extract_tag('author', content)
    hymn_number = extract_tag('hymn_number', content)
    
    return {
        'title': title,
        'lyrics': lyrics,
        'presentation': presentation,
        'author': author,
        'hymn_number': hymn_number,
        'raw': content
    }, None

def get_verse_labels(lyrics):
    """Return list of verse labels found in lyrics like V1, V2, C, B, etc."""
    return re.findall(r'\[([^\]]+)\]', lyrics)

def analyze_presentation(song, filepath):
    """Check presentation tag for errors."""
    issues = []
    lyrics = song['lyrics']
    presentation = song['presentation']
    
    if not presentation:
        return issues
    
    # Get all verse labels defined in lyrics
    defined_labels = set(get_verse_labels(lyrics))
    
    # Parse presentation entries
    pres_entries = presentation.strip().split()
    
    for entry in pres_entries:
        if entry not in defined_labels:
            issues.append(f"Presentation references '{entry}' which is not defined in lyrics (defined: {sorted(defined_labels)})")
    
    # Check for duplicate consecutive entries
    for i in range(len(pres_entries)-1):
        if pres_entries[i] == pres_entries[i+1]:
            issues.append(f"Presentation has consecutive duplicate: '{pres_entries[i]} {pres_entries[i+1]}'")
    
    return issues

def analyze_verse_numbering(song, filepath):
    """Check verse labels for consistency and sequential numbering."""
    issues = []
    lyrics = song['lyrics']
    if not lyrics:
        return issues
    
    labels = get_verse_labels(lyrics)
    if not labels:
        return issues
    
    # Check for verse labels
    verse_nums = []
    seen_labels = []
    label_types = set()
    
    for label in labels:
        label_types.add(label)
        # Check for verse numbers
        vm = re.match(r'^V(\d+)$', label)
        if vm:
            verse_nums.append(int(vm.group(1)))
        # Check for non-standard labels
        if re.match(r'^Verse\s*\d*$', label, re.IGNORECASE):
            issues.append(f"Non-standard verse label '{label}' (should be V1, V2, etc.)")
        elif re.match(r'^Chorus$', label, re.IGNORECASE) or re.match(r'^Ref$', label, re.IGNORECASE):
            issues.append(f"Non-standard chorus label '{label}' (should be 'C')")
        elif re.match(r'^Bridge$', label, re.IGNORECASE):
            issues.append(f"Non-standard bridge label '{label}' (should be 'B')")
        # Check for duplicate section labels
        if label in seen_labels:
            issues.append(f"Duplicate verse label '{label}' in lyrics")
        seen_labels.append(label)
    
    # Check sequential numbering of verses
    if verse_nums:
        verse_nums_sorted = sorted(verse_nums)
        expected = list(range(1, len(verse_nums)+1))
        if verse_nums_sorted != expected:
            issues.append(f"Verse numbers not sequential: found {verse_nums_sorted}, expected {expected}")
        elif verse_nums != verse_nums_sorted:
            issues.append(f"Verse labels out of order: {['V'+str(n) for n in verse_nums]}")
    
    return issues

def analyze_title_vs_filename(song, filepath):
    """Compare filename with title tag."""
    issues = []
    filename = os.path.basename(filepath)
    title = song['title']
    
    if not title:
        issues.append(f"Missing or empty <title> tag")
        return issues
    
    # Normalize for comparison: remove number prefix, punctuation differences
    def normalize(s):
        # Remove leading number and dot
        s = re.sub(r'^\d+[a-z]?\.\s*', '', s)
        # Remove extra spaces
        s = re.sub(r'\s+', ' ', s).strip()
        return s
    
    fn_norm = normalize(filename)
    title_norm = normalize(title)
    
    # They should be the same (title includes number prefix, filename too)
    if filename != title:
        # Check if it's just comma vs no-comma difference
        fn_nocomma = filename.replace(',', '')
        title_nocomma = title.replace(',', '')
        if fn_nocomma == title_nocomma:
            pass  # comma difference only - ignore
        else:
            # Check for meaningful difference
            if fn_norm.lower() != title_norm.lower():
                issues.append(f"Filename '{filename}' differs from title '{title}'")
    
    return issues

def check_numbering_in_hymnal(hymnal_dir, files_in_dir):
    """Check number sequence in a hymnal directory."""
    issues = []
    numbers = {}
    
    for filepath in files_in_dir:
        filename = os.path.basename(filepath)
        m = re.match(r'^(\d+)([a-z]?)\.\s', filename)
        if m:
            num = int(m.group(1))
            suffix = m.group(2)
            key = num
            if key in numbers and not suffix:
                issues.append(f"Duplicate number {num}: '{numbers[key]}' and '{filename}'")
            else:
                if key not in numbers:
                    numbers[key] = filename
    
    if numbers:
        sorted_nums = sorted(numbers.keys())
        min_n = sorted_nums[0]
        max_n = sorted_nums[-1]
        for i in range(min_n, max_n+1):
            if i not in numbers:
                # Check if it's a known gap (like 113a exists but 113 also exists)
                issues.append(f"Missing number {i} in sequence (range {min_n}-{max_n})")
    
    return issues

def detect_polish_typos(lyrics, title):
    """Detect potential Polish spelling/typo issues."""
    issues = []
    
    # Common Polish typo patterns
    # 1. Doubled letters that are unusual in Polish
    # This is hard without a full dictionary, so let's look for specific patterns
    
    # Check for obvious doubled consonants that don't appear in Polish
    # (Polish doesn't usually double consonants like rr, tt, mm, etc. except in compounds)
    text = lyrics + " " + title
    
    # Look for patterns like missing diacritics in context
    # e.g., "sie" instead of "się", "ze" instead of "że" (hard to distinguish without context)
    
    # Look for specific common errors
    # "swiety" instead of "święty"
    if re.search(r'\bswiety\b', text, re.IGNORECASE):
        issues.append("Possible missing diacritics: 'swiety' should be 'święty'")
    if re.search(r'\bboze\b', text, re.IGNORECASE):
        issues.append("Possible missing diacritics: 'boze' should be 'Boże'")
    if re.search(r'\bjuz\b', text, re.IGNORECASE):
        issues.append("Possible missing diacritics: 'juz' should be 'już'")
    if re.search(r'\bmoze\b', text, re.IGNORECASE):
        issues.append("Possible missing diacritics: 'moze' should be 'może'")
    
    return issues

def analyze_title_vs_first_line(song, filepath):
    """Check if title matches first meaningful line of lyrics."""
    issues = []
    title = song['title']
    lyrics = song['lyrics']
    
    if not title or not lyrics:
        return issues
    
    # Get title without number prefix
    title_no_num = re.sub(r'^\d+[a-z]?\.\s*', '', title).strip()
    
    # Get first non-empty, non-chord, non-label line from lyrics
    lines = lyrics.split('\n')
    first_lyric_line = ''
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^\[[^\]]+\]$', stripped):  # verse label
            continue
        if stripped.startswith('.'):  # chord line
            continue
        # Remove leading number like "1." or " 1."
        clean = re.sub(r'^\s*\d+\.\s*', '', stripped).strip()
        if clean:
            first_lyric_line = clean
            break
    
    if not first_lyric_line:
        return issues
    
    # Compare (case-insensitive, ignore punctuation differences except major ones)
    def normalize_for_compare(s):
        s = s.lower()
        s = re.sub(r'[,;:!?"\']', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s
    
    title_norm = normalize_for_compare(title_no_num)
    line_norm = normalize_for_compare(first_lyric_line)
    
    # Check if title is roughly the beginning of the first line or vice versa
    # Only flag if they're significantly different
    if title_norm and line_norm:
        # If title is not a prefix/substring of first line and vice versa
        if title_norm not in line_norm and line_norm not in title_norm:
            # Check word overlap
            title_words = set(title_norm.split())
            line_words = set(line_norm.split())
            overlap = title_words & line_words
            if len(overlap) == 0 and len(title_words) > 0:
                issues.append(f"Title '{title_no_num}' seems unrelated to first lyric line '{first_lyric_line[:60]}'")
            elif len(overlap) < min(2, len(title_words)) and len(title_words) > 2:
                pass  # might be intentional
    
    return issues

# Main analysis
all_files = get_all_files()
print(f"Total files to analyze: {len(all_files)}", flush=True)

# Group by hymnal
hymnals = defaultdict(list)
for f in all_files:
    hymnal = os.path.dirname(f)
    hymnals[hymnal].append(f)

# Results storage
results = {
    'presentation_errors': [],
    'verse_formatting': [],
    'title_filename_mismatch': [],
    'numbering_issues': [],
    'title_content_mismatch': [],
    'spelling_issues': [],
    'missing_title': [],
    'parse_errors': [],
}

# Analyze each file
file_count = 0
for filepath in all_files:
    file_count += 1
    song, err = parse_song(filepath)
    
    if err or song is None:
        results['parse_errors'].append((filepath, f"Parse error: {err}"))
        continue
    
    rel_path = os.path.relpath(filepath, BASE)
    
    # 1. Missing title
    if not song['title']:
        results['missing_title'].append((rel_path, "Missing <title> tag"))
    
    # 2. Presentation errors
    pres_issues = analyze_presentation(song, filepath)
    for issue in pres_issues:
        results['presentation_errors'].append((rel_path, issue))
    
    # 3. Verse formatting
    verse_issues = analyze_verse_numbering(song, filepath)
    for issue in verse_issues:
        results['verse_formatting'].append((rel_path, issue))
    
    # 4. Title vs filename
    tf_issues = analyze_title_vs_filename(song, filepath)
    for issue in tf_issues:
        results['title_filename_mismatch'].append((rel_path, issue))
    
    # 5. Title vs content
    tc_issues = analyze_title_vs_first_line(song, filepath)
    for issue in tc_issues:
        results['title_content_mismatch'].append((rel_path, issue))
    
    if file_count % 100 == 0:
        print(f"  Processed {file_count}/{len(all_files)}...", flush=True)

# 5. Numbering per hymnal
for hymnal_dir, hymnal_files in sorted(hymnals.items()):
    num_issues = check_numbering_in_hymnal(hymnal_dir, hymnal_files)
    hymnal_name = os.path.relpath(hymnal_dir, BASE)
    for issue in num_issues:
        results['numbering_issues'].append((hymnal_name, issue))

print("\n\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)

# Print results
sections = [
    ('CATEGORY 3: PRESENTATION TAG ERRORS', 'presentation_errors'),
    ('CATEGORY 6: VERSE FORMATTING INCONSISTENCIES', 'verse_formatting'),
    ('CATEGORY 4: FILENAME vs TITLE DISCREPANCIES', 'title_filename_mismatch'),
    ('CATEGORY 5: NUMBERING INCONSISTENCIES', 'numbering_issues'),
    ('CATEGORY 2: TITLE vs CONTENT DISCREPANCIES', 'title_content_mismatch'),
    ('PARSE ERRORS', 'parse_errors'),
    ('MISSING TITLES', 'missing_title'),
]

for section_name, key in sections:
    items = results[key]
    print(f"\n{'='*80}")
    print(f"{section_name} ({len(items)} issues)")
    print('='*80)
    for item in items:
        print(f"  FILE: {item[0]}")
        print(f"  ISSUE: {item[1]}")
        print()

print(f"\nTotal issues found:")
for section_name, key in sections:
    print(f"  {section_name}: {len(results[key])}")

