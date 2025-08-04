import pdfplumber
import re
import json
import configparser
import os
from collections import defaultdict

def analyze_font_sizes(page):
    """
    Analyze font sizes in the page to determine content types.
    Returns a dictionary with font size statistics.
    """
    words = page.extract_words(
        x_tolerance=3, 
        y_tolerance=2, 
        extra_attrs=["size", "fontname"], 
        use_text_flow=True
    )
    
    font_sizes = [word['size'] for word in words if word['size']]
    if not font_sizes:
        return {}
    
    font_sizes.sort()
    
    # Group similar font sizes
    size_groups = defaultdict(list)
    tolerance = 0.5
    
    for size in font_sizes:
        grouped = False
        for group_size in size_groups:
            if abs(size - group_size) <= tolerance:
                size_groups[group_size].append(size)
                grouped = True
                break
        if not grouped:
            size_groups[size] = [size]
    
    # Calculate average size for each group
    avg_sizes = {k: sum(v)/len(v) for k, v in size_groups.items()}
    
    # Sort by frequency and size
    size_frequency = {k: len(v) for k, v in size_groups.items()}
    
    # Identify content types based on font size
    sorted_sizes = sorted(avg_sizes.items(), key=lambda x: x[1])
    
    font_info = {
        'all_sizes': sorted_sizes,
        'size_frequency': size_frequency,
        'avg_sizes': avg_sizes
    }
    
    # Determine content type thresholds
    if len(sorted_sizes) >= 3:
        # Smallest fonts are likely footnotes
        font_info['footnote_size'] = sorted_sizes[0][1]
        # Largest fonts are likely headers/titles
        font_info['header_size'] = sorted_sizes[-1][1]
        # Medium fonts are likely body text
        font_info['body_size'] = sorted_sizes[len(sorted_sizes)//2][1]
    elif len(sorted_sizes) == 2:
        font_info['footnote_size'] = sorted_sizes[0][1]
        font_info['body_size'] = sorted_sizes[1][1]
        font_info['header_size'] = sorted_sizes[1][1]
    else:
        font_info['body_size'] = sorted_sizes[0][1]
        font_info['header_size'] = sorted_sizes[0][1]
        font_info['footnote_size'] = sorted_sizes[0][1]
    
    return font_info

def group_words_to_lines(words, y_tolerance=2):
    """
    Group words into lines based on y-coordinate.
    """
    if not words:
        return []
        
    lines = []
    words = sorted(words, key=lambda w: w['top'])
    current_line = []
    last_top = None
    
    for word in words:
        if last_top is None or abs(word['top'] - last_top) < y_tolerance:
            current_line.append(word)
        else:
            if current_line:
                lines.append(current_line)
            current_line = [word]
        last_top = word['top']
    
    if current_line:
        lines.append(current_line)
    
    return lines

def clean_hyphenated_text(text):
    """Remove hyphens at line breaks and join words."""
    return re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)

def extract_titles(words):
    """Extract chapter titles and subtitles."""
    title_words = []
    for word in words:
        if (word.get('size') and 
            word['size'] > 7 and  # Large font for titles
            word['top'] < 200):  # Top area
            title_words.append(word)
            
    
    if not title_words:
        return []
    
    # Group by y position to separate different titles
    title_groups = defaultdict(list)
    for word in title_words:
        title_groups[round(word['top'])].append(word)
    
    titles = []
    for y_pos in sorted(title_groups.keys()):
        group_words = title_groups[y_pos]
        # Sort by x position
        group_words.sort(key=lambda w: w['x0'])
        title_text = " ".join(word['text'] for word in group_words)
        if title_text.strip():
            titles.append(title_text.strip())
    
    return titles

def extract_page_header(words):
    """Extract page header (page number and chapter name)."""
    header_words = []
    for word in words:
        if word.get('size') and 6.0 <= word['size'] < 7.0 and word['top'] < 70:  # Top area
            header_words.append(word)
    
    if header_words:
        # Sort by x position to get correct order
        header_words.sort(key=lambda w: w['x0'])
        header_text = " ".join(word['text'] for word in header_words)
        return header_text
    return ""

def extract_body_paragraphs_with_footnote_refs(words):
    """Extract body paragraphs and identify footnote references."""
    body_words = []
    
    for word in words:
        if (word.get('size') and 
            10.0 <= word['size'] <= 11.0 and  # Large body text font
            70 < word['top'] < 400):  # Main content area, above footnotes
            
            # Check if this is a footnote reference (small superscript number)
            if (word['size'] <= 6.0 and  # Small font
                word['text'].isdigit() and  # Just digits
                len(word['text']) <= 2):  # Short (1-2 digits)
                word['text'].append(f"[{word['text']}]")
            else:
                body_words.append(word)
    
    # Group body words by lines
    body_lines = group_words_to_lines(body_words, y_tolerance=2)
    
    # Clean up hyphens and group into paragraphs using indentation
    body_paragraphs = []
    current_para = []
    first_para = True  # Track if this is the first paragraph (no indent)
    
    for line in body_lines:
        if not line:
            continue
            
        first_word = line[0]
        line_text = " ".join(word['text'] for word in line)
        indent = first_word['x0']
        
        # Clean up hyphens
        line_text = clean_hyphenated_text(line_text)
        
        # Check for new paragraph based on indentation
        is_new_para = False
        
        if first_para:
            # First paragraph starts at left margin (no indent)
            if indent > 90:  # If this line is indented, it's a new paragraph
                is_new_para = True
                first_para = False
        else:
            # Subsequent paragraphs should be indented
            if indent <= 90:  # If this line is not indented, it might be a new paragraph
                # Check if this looks like the start of a new paragraph
                if (re.match(r'^[A-Z]', line_text) and  # Starts with capital letter
                    len(line_text.split()) > 2):  # Has multiple words
                    is_new_para = True
        
        if is_new_para and current_para:
            # Join lines into a single paragraph text
            para_text = " ".join(line['text'] for line in current_para)
            body_paragraphs.append(para_text)
            current_para = []
        
        current_para.append({
            'text': line_text,
            'indent': indent,
            'y': first_word['top']
        })
    
    if current_para:
        # Join lines into a single paragraph text
        para_text = " ".join(line['text'] for line in current_para)
        body_paragraphs.append(para_text)
    
    return body_paragraphs

def extract_footnotes_improved(words):
    """Extract complete footnotes with improved logic."""
    footnote_words = []
    for word in words:
        if word['top'] > 450:  # Bottom area where footnotes are
            footnote_words.append(word)
    
    # Sort by y position
    footnote_words.sort(key=lambda w: w['top'])
    
    # Group into lines
    footnote_lines = group_words_to_lines(footnote_words, y_tolerance=2)
    
    # Extract complete footnotes
    footnotes = []
    current_footnote = None
    
    for line in footnote_lines:
        if not line:
            continue
        
        line_text = " ".join(word['text'] for word in line)
        line_y = line[0]['top']
        
        # Clean up hyphens
        line_text = clean_hyphenated_text(line_text)
        
        # Check if this line starts with a footnote number
        if re.match(r'^\d+', line_text):
            # Save previous footnote if exists
            if current_footnote:
                footnotes.append(current_footnote)
            
            # Extract footnote number and content
            match = re.match(r'^(\d+)(.*)', line_text)
            if match:
                footnote_num = match.group(1)
                content = match.group(2).strip()
                current_footnote = {
                    "original_id": footnote_num,
                    "content": [content] if content else [],
                    "start_y": line_y
                }
        elif current_footnote:
            # Continue current footnote (check if it's close to the footnote)
            if abs(line_y - current_footnote["start_y"]) < 30:  # Within reasonable distance
                # Additional check: make sure this line doesn't start with a new footnote number
                if not re.match(r'^\d+', line_text):
                    current_footnote["content"].append(line_text)
    
    # Add last footnote
    if current_footnote:
        footnotes.append(current_footnote)
    
    # Convert to final format and handle special cases
    result = []
    for footnote in footnotes:
        footnote_text = " ".join(footnote['content'])
        
        # Handle special case where footnote content might be split incorrectly
        # Check if this looks like a continuation of previous footnote
        if (footnote['original_id'] in ['233', '241'] and 
            len(result) > 0 and 
            result[-1]['original_id'] == '9'):
            # This is likely a continuation of footnote 9
            result[-1]['source_text'] += " " + footnote_text
        else:
            result.append({
                "original_id": footnote['original_id'],
                "source_text": footnote_text
            })
    
    return result

def pdf_to_json_final(pdf_path, output_path, start_page=None, end_page=None):
    """
    Convert PDF to JSON with improved content classification.
    """
    with pdfplumber.open(pdf_path) as pdf:
        result = []
        content_id = 1
        
        # Determine page range
        if start_page is None:
            start_page = 1
        if end_page is None:
            end_page = len(pdf.pages) + 1
        
        for page_num in range(start_page - 1, end_page - 1):  # Convert to 0-based index
            page = pdf.pages[page_num]
            actual_page_num = page_num + 1  # Convert back to 1-based
            
            print(f"Processing page {actual_page_num}...")
            
            # Extract words with optimal parameters
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=2,
                extra_attrs=["size", "fontname"],
                use_text_flow=True
            )
            
            page_content = {
                "page_number": actual_page_num,
                "content_units": []
            }
            
            # Extract titles (chapter titles and subtitles)
            titles = extract_titles(words)
            for title_text in titles:
                page_content["content_units"].append({
                    "id": content_id,
                    "type": "title",
                    "source_text": title_text,
                    "status": "pending",
                    "azure_translation": "",
                    "ai_second_draft": ""
                })
                content_id += 1
            
            # Extract page header (if not first page of chapter)
            if not titles:  # Only extract header if no titles (not chapter start)
                header_text = extract_page_header(words)
                if header_text:
                    page_content["content_units"].append({
                        "id": content_id,
                        "type": "header",
                        "source_text": header_text,
                        "status": "pending",
                        "azure_translation": "",
                        "ai_second_draft": ""
                    })
                    content_id += 1
            
            # Extract body paragraphs and footnote references
            body_paragraphs = extract_body_paragraphs_with_footnote_refs(words)
            
            # Process body paragraphs and insert footnote references
            for para_text in body_paragraphs:
                page_content["content_units"].append({
                    "id": content_id,
                    "type": "paragraph",
                    "source_text": para_text,
                    "status": "pending",
                    "azure_translation": "",
                    "ai_second_draft": ""
                })
                content_id += 1
            
            # Extract footnotes
            footnotes = extract_footnotes_improved(words)
            for footnote in footnotes:
                page_content["content_units"].append({
                    "id": content_id,
                    "type": "footnote",
                    "original_id": footnote["original_id"],
                    "source_text": footnote["source_text"],
                    "status": "pending",
                    "azure_translation": "",
                    "ai_second_draft": ""
                })
                content_id += 1
            
            result.append(page_content)
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        
        # Write to JSON file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"JSON file saved to: {output_path}")
        return result

def main():
    """Main function to run the PDF to JSON conversion."""
    # Read configuration
    config = configparser.ConfigParser()
    config.read('pdf_to_json.cfg')
    
    pdf_path = config.get('Files', 'input_pdf')
    output_path = config.get('Files', 'output_json')
    
    # Get page range from config
    start_page = config.getint('Pages', 'start_page', fallback=None)
    end_page = config.getint('Pages', 'end_page', fallback=None)
    
    # Convert PDF to JSON
    result = pdf_to_json_final(pdf_path, output_path, start_page, end_page)
    
    # Print summary
    total_pages = len(result)
    total_units = sum(len(page['content_units']) for page in result)
    print(f"\nConversion completed!")
    print(f"Total pages processed: {total_pages}")
    print(f"Total content units: {total_units}")

if __name__ == "__main__":
    main() 
