#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive analysis of OpenSong Polish hymn files - v2 with fixed verse label detection."""

import os
import re
from collections import defaultdict

BASE = "/home/runner/work/Piesni-OpenSong/Piesni-OpenSong"

def get_all_files():
    files = []
    for dirpath, dirnames, filenames in os.walk(BASE):
        dirnames[:] = sorted([d for d in dirnames if d != '.git'])
        for fn in sorted(filenames):
            if fn == 'LICENSE' or fn.endswith('.py') or fn.endswith('.md'):
                continue
            files.append(os.path.join(dirpath, fn))
    return files

def parse_song(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, str(e)
    def extract_tag(tag, text):
        m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', text, re.DOTALL)
        return m.group(1).strip() if m else ''
    return {
        'title': extract_tag('title', content),
        'lyrics': extract_tag('lyrics', content),
        'presentation': extract_tag('presentation', content),
        'raw': content
    }, None

def get_verse_section_labels(lyrics):
    """Extract only real section labels like [V1], [C], [B], [T], [C1], [V2] etc.
    NOT repeat content markers like [: text :]"""
    # Real labels are short identifiers - typically 1-3 chars like V1, C, B, T, C1, V2, etc.
    labels = []
    for m in re.finditer(r'\[([^\]]+)\]', lyrics):
        label = m.group(1).strip()
        # Real section label: short, no newlines, matches pattern like V1, V2, C, C1, B, T, etc.
        if '\n' not in label and ':' not in label and len(label) <= 10:
            if re.match(r'^[A-Za-z]\d*[a-z]?$', label.strip()) or re.match(r'^[A-Za-z]{1,3}\d{0,2}$', label.strip()):
                labels.append(label.strip())
    return labels

def analyze_presentation(song, filepath):
    issues = []
    lyrics = song['lyrics']
    presentation = song['presentation']
    if not presentation:
        return issues
    
    defined_labels = set(get_verse_section_labels(lyrics))
    pres_entries = presentation.strip().split()
    
    for entry in pres_entries:
        if entry not in defined_labels:
            issues.append(f"Presentation references '{entry}' not defined in lyrics (defined: {sorted(defined_labels)})")
    
    return issues

def analyze_verse_numbering(song, filepath):
    issues = []
    lyrics = song['lyrics']
    if not lyrics:
        return issues
    
    labels = get_verse_section_labels(lyrics)
    if not labels:
        return issues
    
    verse_nums = []
    seen = []
    
    for label in labels:
        if label in seen:
            issues.append(f"Duplicate section label [{label}] in lyrics")
        seen.append(label)
        
        vm = re.match(r'^V(\d+)$', label)
        if vm:
            verse_nums.append(int(vm.group(1)))
        
        # Non-standard labels
        if re.match(r'^[Vv]erse\s*\d*$', label):
            issues.append(f"Non-standard label [{label}] (use V1, V2, etc.)")
        elif re.match(r'^[Cc]horus$', label):
            issues.append(f"Non-standard label [{label}] (use C)")
        elif re.match(r'^[Bb]ridge$', label):
            issues.append(f"Non-standard label [{label}] (use B)")
        elif re.match(r'^[Rr]ef\d*$', label):
            issues.append(f"Non-standard label [{label}] (typically use C for chorus)")
    
    if verse_nums:
        sorted_nums = sorted(verse_nums)
        expected = list(range(1, len(verse_nums)+1))
        if sorted_nums != expected:
            issues.append(f"Verse numbers not sequential: found {sorted_nums}, expected {expected}")
        elif verse_nums != sorted_nums:
            issues.append(f"Verse labels out of order: {['V'+str(n) for n in verse_nums]}")
    
    return issues

def analyze_title_vs_filename(song, filepath):
    issues = []
    filename = os.path.basename(filepath)
    title = song['title']
    
    if not title:
        issues.append("Missing <title> tag")
        return issues
    
    if filename == title:
        return issues
    
    # Ignore comma-only differences
    if filename.replace(',', '') == title.replace(',', ''):
        return issues
    
    # Extract the text part (after number prefix if present)
    def strip_num(s):
        return re.sub(r'^\d+[a-z]?\.\s*', '', s).strip()
    
    fn_text = strip_num(filename)
    title_text = strip_num(title)
    
    # Check if number prefix differs
    fn_num_m = re.match(r'^(\d+[a-z]?)\.\s*(.*)', filename)
    title_num_m = re.match(r'^(\d+[a-z]?)\.\s*(.*)', title)
    
    fn_has_num = bool(fn_num_m)
    title_has_num = bool(title_num_m)
    
    if fn_has_num and title_has_num:
        fn_num = fn_num_m.group(1)
        title_num = title_num_m.group(1)
        fn_rest = fn_num_m.group(2)
        title_rest = title_num_m.group(2)
        
        if fn_num != title_num:
            issues.append(f"Number in filename '{fn_num}' differs from number in title '{title_num}' | Filename: '{filename}' | Title: '{title}'")
        
        if fn_rest != title_rest:
            # Ignore comma differences
            if fn_rest.replace(',', '') != title_rest.replace(',', ''):
                issues.append(f"Text differs: filename has '{fn_rest}' but title has '{title_rest}'")
    elif fn_has_num and not title_has_num:
        # Filename has number but title doesn't
        fn_rest = fn_num_m.group(2)
        if fn_rest.replace(',','') != title.replace(',','') and fn_text.replace(',','') != title.replace(',',''):
            issues.append(f"Filename has number prefix but title does not | Filename: '{filename}' | Title: '{title}'")
    elif not fn_has_num and title_has_num:
        title_rest = title_num_m.group(2)
        if title_rest.replace(',','') != filename.replace(',',''):
            issues.append(f"Title has number prefix but filename does not | Filename: '{filename}' | Title: '{title}'")
    else:
        # Neither has number - direct comparison
        if fn_text.replace(',','').strip() != title_text.replace(',','').strip():
            issues.append(f"Filename '{filename}' differs from title '{title}'")
    
    return issues

def check_numbering(hymnal_dir, files_in_dir):
    issues = []
    numbers = {}
    suffixed = {}
    
    for filepath in files_in_dir:
        filename = os.path.basename(filepath)
        m = re.match(r'^(\d+)([a-z]?)\.', filename)
        if m:
            num = int(m.group(1))
            suffix = m.group(2)
            if suffix:
                suffixed[num] = suffixed.get(num, []) + [filename]
            else:
                if num in numbers:
                    issues.append(f"Duplicate number {num}: '{numbers[num]}' and '{filename}'")
                else:
                    numbers[num] = filename
    
    if numbers:
        sorted_nums = sorted(numbers.keys())
        min_n, max_n = sorted_nums[0], sorted_nums[-1]
        for i in range(min_n, max_n+1):
            if i not in numbers and i not in suffixed:
                issues.append(f"Missing number {i} in sequence {min_n}-{max_n}")
    
    return issues

def analyze_spelling(lyrics, title, filepath):
    """Look for specific Polish spelling/diacritics issues."""
    issues = []
    text = lyrics + " " + title
    
    # Check for words that should have Polish diacritics but clearly don't
    # These are common Polish words - if found without diacritics they're errors
    checks = [
        (r'\bBoze\b', 'Boże', 'missing ż'),
        (r'\bswiety\b', 'święty', 'missing ś,ę'),
        (r'\bJuz\b', 'Już', 'missing ż'),
        (r'\bjuz\b', 'już', 'missing ż'),
        (r'\bmoze\b', 'może', 'missing ż'),
        (r'\bMoze\b', 'Może', 'missing ż'),
        (r'\bswiata\b', 'świata', 'missing ś'),
        (r'\bswiat\b(?!ł)', 'świat', 'missing ś'),
        (r'\bpan\b', 'Pan', 'capitalization (religious context)'),
        # doubled letters unusual in Polish
        (r'\bll\b', 'possible doubled l', 'doubled consonant'),
    ]
    
    for pattern, correct, desc in checks:
        if re.search(pattern, text):
            issues.append(f"Possible spelling issue ({desc}): '{pattern}' should be '{correct}'")
    
    return issues

def get_first_lyric_line(lyrics):
    """Get first non-empty, non-chord, non-label line."""
    for line in lyrics.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^\[[^\]]*\]$', stripped):  # verse label line
            continue
        if stripped.startswith('.'):  # chord line
            continue
        # Remove leading verse number like "1." 
        clean = re.sub(r'^\s*\d+\.\s*', '', stripped).strip()
        if clean:
            return clean
    return ''

def analyze_title_vs_content(song, filepath):
    """Check meaningful discrepancy between title text and first lyric line."""
    issues = []
    title = song['title']
    lyrics = song['lyrics']
    if not title or not lyrics:
        return issues
    
    title_text = re.sub(r'^\d+[a-z]?\.\s*', '', title).strip()
    # Remove parenthetical info from title for comparison
    title_clean = re.sub(r'\s*\([^)]*\)\s*', ' ', title_text).strip()
    
    first_line = get_first_lyric_line(lyrics)
    if not first_line:
        return issues
    
    def norm(s):
        s = s.lower()
        s = re.sub(r'[,;:!?"\'\-–—]', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s
    
    title_norm = norm(title_clean)
    line_norm = norm(first_line)
    
    if not title_norm or not line_norm:
        return issues
    
    # Check if title words appear in first line or vice versa
    title_words = [w for w in title_norm.split() if len(w) > 3]
    line_words = set(line_norm.split())
    
    if len(title_words) == 0:
        return issues
    
    overlap = sum(1 for w in title_words if w in line_words)
    
    # Flag only if zero word overlap and title has meaningful words
    if overlap == 0 and len(title_words) >= 2:
        issues.append(f"Title '{title_text}' appears unrelated to first lyric line: '{first_line[:70]}'")
    
    return issues

# ---- Main ----
all_files = get_all_files()
print(f"Analyzing {len(all_files)} files...", flush=True)

hymnals = defaultdict(list)
for f in all_files:
    hymnals[os.path.dirname(f)].append(f)

results = defaultdict(list)

for filepath in all_files:
    song, err = parse_song(filepath)
    if err or not song:
        results['parse_errors'].append((filepath, err))
        continue
    
    rel = os.path.relpath(filepath, BASE)
    
    for issue in analyze_presentation(song, filepath):
        results['presentation'].append((rel, issue))
    
    for issue in analyze_verse_numbering(song, filepath):
        results['verse_fmt'].append((rel, issue))
    
    for issue in analyze_title_vs_filename(song, filepath):
        results['title_filename'].append((rel, issue))
    
    for issue in analyze_title_vs_content(song, filepath):
        results['title_content'].append((rel, issue))
    
    for issue in analyze_spelling(song['lyrics'], song['title'], filepath):
        results['spelling'].append((rel, issue))

for hymnal_dir, hymnal_files in sorted(hymnals.items()):
    hymnal_name = os.path.relpath(hymnal_dir, BASE)
    for issue in check_numbering(hymnal_dir, hymnal_files):
        results['numbering'].append((hymnal_name, issue))

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
for k, v in results.items():
    print(f"  {k}: {len(v)} issues")

# Detailed output
sections = [
    ('CATEGORY 3 — PRESENTATION TAG ERRORS', 'presentation'),
    ('CATEGORY 6 — VERSE FORMATTING (non-sequential / non-standard labels / duplicates)', 'verse_fmt'),
    ('CATEGORY 4 — FILENAME vs TITLE DISCREPANCIES', 'title_filename'),
    ('CATEGORY 5 — NUMBERING INCONSISTENCIES', 'numbering'),
    ('CATEGORY 2 — TITLE vs LYRICS CONTENT DISCREPANCIES', 'title_content'),
    ('CATEGORY 1 — SPELLING / DIACRITICS ISSUES', 'spelling'),
    ('PARSE ERRORS', 'parse_errors'),
]

for name, key in sections:
    items = results[key]
    print(f"\n{'='*80}")
    print(f"{name}  [{len(items)} issues]")
    print('='*80)
    for path, issue in items:
        print(f"  • {path}")
        print(f"    → {issue}")

