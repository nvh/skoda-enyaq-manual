#!/usr/bin/env python3
"""
Create a single HTML file from the Skoda manual with proper header hierarchy
and embedded images. Preserves original HTML structure.
"""

import json
import re
import base64
from pathlib import Path
from html.parser import HTMLParser

OUTPUT_DIR = Path("manual_output")
IMAGES_DIR = OUTPUT_DIR / "images"
HTML_FILE = OUTPUT_DIR / "manual.html"


def get_image_as_base64(img_path):
    """Convert image to base64 data URI"""
    try:
        if img_path.startswith("../"):
            clean_path = re.sub(r'^(\.\./)+', '', img_path)
            full_path = OUTPUT_DIR / clean_path
        elif img_path.startswith("images/"):
            full_path = OUTPUT_DIR / img_path
        else:
            full_path = Path(img_path)

        if not full_path.exists():
            return None

        content = full_path.read_bytes()
        suffix = full_path.suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp'
        }
        mime = mime_types.get(suffix, 'image/png')
        b64 = base64.b64encode(content).decode('utf-8')
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        return None


def url_to_local_path(url):
    """Convert remote URL to local image path"""
    # Decode HTML entities
    url = url.replace('&amp;', '&')

    if 'key=' in url:
        # Extract key parameter
        match = re.search(r'key=([^&]+)', url)
        if match:
            key = match.group(1)
            filename = re.sub(r'[^\w.-]', '_', key)
            if '.svg' in key.lower() or '.svg' in url.lower():
                if not filename.endswith('.svg'):
                    filename += '.svg'
            elif not any(filename.endswith(ext) for ext in ['.png', '.jpg', '.gif', '.svg']):
                filename += '.png'
            return f"images/{filename}"
    return None


def process_source_html(html_content):
    """Process the source HTML to clean it up and make it display properly"""

    # Remove outer html/div wrappers
    html = re.sub(r'^<html[^>]*><div[^>]*><div class="topic-content">', '', html_content)
    html = re.sub(r'</div></div></html>$', '', html)

    # Remove non-standard </img> closing tags
    html = html.replace('</img>', '')

    # Convert warning/caution panels to proper structure
    # Pattern: <div data-role="signalword-panel"><img...><p>WAARSCHUWING</p></div>
    html = re.sub(
        r'<div[^>]*data-role="signalword-panel"[^>]*>',
        r'<div class="signalword-panel">',
        html
    )

    # Convert data-type="titel" paragraphs to bold headers
    html = re.sub(
        r'<p[^>]*data-type="titel"[^>]*data-role="bridgehead"[^>]*>([^<]*)</p>',
        r'<p class="sub-header"><strong>\1</strong></p>',
        html
    )
    html = re.sub(
        r'<p[^>]*data-role="bridgehead"[^>]*data-type="titel"[^>]*>([^<]*)</p>',
        r'<p class="sub-header"><strong>\1</strong></p>',
        html
    )

    # Clean up empty paragraphs
    html = re.sub(r'<p[^>]*>\s*</p>', '', html)

    # Remove unnecessary data attributes but keep structure
    html = re.sub(r'\s+data-[a-z-]+="[^"]*"', '', html)
    html = re.sub(r'\s+id="[^"]*"', '', html)
    html = re.sub(r'\s+class="(?!signalword-panel|sub-header)[^"]*"', '', html)
    html = re.sub(r'\s+media-link=""', '', html)
    html = re.sub(r'\s+checked-link="[^"]*"', '', html)
    html = re.sub(r'\s+alt=""', '', html)

    # Re-add important classes
    html = re.sub(r'<p><strong>([^<]+)</strong></p>', r'<p class="sub-header"><strong>\1</strong></p>', html)

    # Remove empty/broken links but keep their text content
    html = re.sub(r'<a[^>]*href="#"[^>]*>([^<]*)</a>', r'\1', html)
    html = re.sub(r'<a[^>]*href="#"[^>]*>(.*?)</a>', r'\1', html, flags=re.DOTALL)

    return html


def embed_images_in_html(html_content):
    """Replace image URLs with embedded base64 data"""

    def replace_img(match):
        full_tag = match.group(0)
        src_match = re.search(r'data-src="([^"]+)"', full_tag) or re.search(r'src="([^"]+)"', full_tag)

        if not src_match:
            return full_tag

        src = src_match.group(1).replace('&amp;', '&')

        # Determine sizing based on image type
        is_svg = '.svg' in src.lower()
        is_qr = 'imgqr' in src.lower()

        if is_qr:
            style = 'width: 150px; height: 150px;'
        elif is_svg:
            style = 'width: 24px; height: 24px; vertical-align: middle; display: inline;'
        else:
            style = 'max-width: 100%; height: auto;'

        # Try to get local path and embed
        local_path = url_to_local_path(src)
        if local_path:
            data_uri = get_image_as_base64(local_path)
            if data_uri:
                return f'<img src="{data_uri}" style="{style}">'

        # Fallback to original URL
        return f'<img src="{src}" style="{style}">'

    return re.sub(r'<img[^>]+>', replace_img, html_content)


def create_html():
    """Create single HTML file from all topics"""
    print("Creating HTML file...")

    index_file = OUTPUT_DIR / "index.json"
    with open(index_file, 'r', encoding='utf-8') as f:
        topics = json.load(f)

    print(f"Processing {len(topics)} topics...")

    html_parts = ['''<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Škoda Enyaq Handleiding</title>
    <style>
        :root {
            --bg-color: #ffffff;
            --text-color: #333333;
            --header-color: #1a5d1a;
            --link-color: #0066cc;
            --border-color: #dddddd;
            --blockquote-bg: #fff3cd;
            --blockquote-border: #ffc107;
        }

        * { box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--bg-color);
            margin: 0;
            padding: 20px;
        }

        .main-content {
            max-width: 900px;
            margin: 0 auto;
        }

        h1 { font-size: 2.2em; color: var(--header-color); border-bottom: 3px solid var(--header-color); padding-bottom: 10px; margin-top: 40px; }
        h2 { font-size: 1.8em; color: var(--header-color); border-bottom: 2px solid var(--border-color); padding-bottom: 8px; margin-top: 35px; }
        h3 { font-size: 1.5em; color: var(--header-color); margin-top: 30px; }
        h4 { font-size: 1.3em; color: var(--header-color); margin-top: 25px; }
        h5 { font-size: 1.1em; color: var(--header-color); margin-top: 20px; }
        h6 { font-size: 1em; color: var(--header-color); margin-top: 15px; }

        /* Sticky headers - stacked by level */
        h2.category-header, .topic-section h2 {
            position: sticky;
            top: 0;
            background: var(--bg-color);
            padding: 12px 0;
            margin-top: 0;
            z-index: 16;
            border-bottom: 1px solid var(--border-color);
        }
        h3.category-header, .topic-section h3 {
            position: sticky;
            top: 52px;
            background: var(--bg-color);
            padding: 16px 0 10px 0;
            margin-top: 0;
            z-index: 15;
            border-bottom: 1px solid var(--border-color);
        }
        h4.category-header, .topic-section h4 {
            position: sticky;
            top: 106px;
            background: var(--bg-color);
            padding: 14px 0 8px 0;
            margin-top: 0;
            z-index: 14;
            border-bottom: 1px solid var(--border-color);
        }
        h5.category-header, .topic-section h5 {
            position: sticky;
            top: 156px;
            background: var(--bg-color);
            padding: 12px 0 6px 0;
            margin-top: 0;
            z-index: 13;
            border-bottom: 1px solid var(--border-color);
        }
        h6.category-header, .topic-section h6 {
            position: sticky;
            top: 200px;
            background: var(--bg-color);
            padding: 10px 0 5px 0;
            margin-top: 0;
            z-index: 12;
            border-bottom: 1px solid var(--border-color);
        }

        img {
            vertical-align: middle;
        }

        a { color: var(--link-color); text-decoration: none; }
        a:hover { text-decoration: underline; }

        ul, ol { padding-left: 25px; margin: 10px 0; }
        li { margin: 5px 0; }
        li p { margin: 0; display: inline; }

        /* Definition lists for icon blocks */
        dl { margin: 15px 0; }
        dt { display: inline-block; vertical-align: top; width: 40px; }
        dd { display: inline-block; vertical-align: top; width: calc(100% - 50px); margin-left: 10px; margin-bottom: 10px; }
        dd p { margin: 0 0 5px 0; }

        /* Sub-headers within content */
        .sub-header {
            margin-top: 25px;
            margin-bottom: 10px;
        }
        .sub-header strong {
            font-size: 1.1em;
        }

        section { margin: 10px 0; }

        /* Warning/caution panels - icon and text on same line */
        .signalword-panel {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 15px 0 5px 0;
        }
        .signalword-panel img {
            flex-shrink: 0;
        }
        .signalword-panel p {
            margin: 0;
            font-weight: bold;
        }

        /* Ensure inline images stay inline */
        span img {
            display: inline;
            vertical-align: middle;
        }
        p img {
            display: inline;
            vertical-align: middle;
        }

        blockquote {
            background-color: var(--blockquote-bg);
            border-left: 4px solid var(--blockquote-border);
            padding: 10px 15px;
            margin: 15px 0;
        }

        .toc {
            background-color: #f8f9fa;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0 40px 0;
        }
        .toc h2 { margin-top: 0; border-bottom: none; font-size: 1.3em; }
        .toc ol { padding-left: 20px; margin: 5px 0; }
        .toc > ol { padding-left: 15px; }
        .toc li { margin: 2px 0; font-size: 0.9em; }
        .toc a { display: inline-block; padding: 1px 0; }

        /* Sidebar layout for wide screens */
        @media (min-width: 1200px) {
            body {
                display: flex;
                padding: 0;
            }
            .toc {
                position: fixed;
                left: 0;
                top: 0;
                width: 300px;
                height: 100vh;
                overflow-y: auto;
                margin: 0;
                border-radius: 0;
                border: none;
                border-right: 1px solid var(--border-color);
                padding: 20px;
                box-sizing: border-box;
            }
            .main-content {
                margin-left: 300px;
                padding: 20px 40px;
                max-width: 900px;
            }
        }

        @media (min-width: 1500px) {
            .toc {
                width: 350px;
            }
            .main-content {
                margin-left: 350px;
            }
        }

        .topic-section {
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        .topic-section:last-child { border-bottom: none; }

        .category-header {
            margin-top: 40px;
            margin-bottom: 10px;
            color: var(--header-color);
        }

        @media print {
            body { max-width: none; padding: 0; }
            .toc { page-break-after: always; }
            h1, h2, h3 { page-break-after: avoid; }
        }

        @media (max-width: 600px) {
            body { padding: 10px; }
            h1 { font-size: 1.6em; }
            h2 { font-size: 1.4em; }
            h3 { font-size: 1.2em; }
            h4 { font-size: 1.1em; }
            h5, h6 { font-size: 1em; }

            /* Ensure headers don't overflow */
            h1, h2, h3, h4, h5, h6 {
                word-wrap: break-word;
                overflow-wrap: break-word;
                hyphens: auto;
            }

            /* Adjust sticky positions for smaller headers */
            h3.category-header, .topic-section h3 { top: 45px; }
            h4.category-header, .topic-section h4 { top: 88px; }
            h5.category-header, .topic-section h5 { top: 128px; }
            h6.category-header, .topic-section h6 { top: 165px; }
        }
    </style>
</head>
<body>
''']

    def make_anchor(path):
        """Create unique anchor from full path"""
        anchor = path.lower()
        anchor = re.sub(r'[^\w\s/-]', '', anchor)
        anchor = re.sub(r'[\s/]+', '-', anchor)
        return anchor

    # Build TOC
    html_parts.append('    <nav class="toc">\n        <h2>Inhoudsopgave</h2>\n')
    prev_depth = -1
    for topic in topics:
        depth = topic['path'].count('/')
        label = topic['label']
        anchor = make_anchor(topic['path'])
        is_category = topic.get('is_category', False) or topic.get('id') is None

        if depth > prev_depth:
            for _ in range(depth - prev_depth):
                html_parts.append('<ol>\n')
        elif depth < prev_depth:
            for _ in range(prev_depth - depth):
                html_parts.append('</li>\n</ol>\n')
            if prev_depth >= 0:
                html_parts.append('</li>\n')
        else:
            if prev_depth >= 0:
                html_parts.append('</li>\n')

        if is_category:
            html_parts.append(f'<li><strong>{label}</strong>\n')
        else:
            html_parts.append(f'<li><a href="#{anchor}">{label}</a>\n')
        prev_depth = depth

    for _ in range(prev_depth + 1):
        html_parts.append('</li>\n</ol>\n')
    html_parts.append('    </nav>\n\n')

    # Start main content wrapper
    html_parts.append('    <div class="main-content">\n')
    html_parts.append('    <h1>Škoda Enyaq Handleiding</h1>\n')

    # Add content for each topic
    for i, topic in enumerate(topics):
        depth = topic['path'].count('/')
        label = topic['label']
        anchor = make_anchor(topic['path'])
        is_category = topic.get('is_category', False) or topic.get('id') is None

        header_level = min(depth + 1, 6)

        if is_category:
            html_parts.append(f'    <h{header_level} class="category-header">{label}</h{header_level}>\n\n')
            continue

        # Skip the main "Handleiding" topic as it's just the index
        if topic['path'] == 'Handleiding':
            continue

        # Read raw JSON content
        topic_dir = OUTPUT_DIR / topic['path']
        json_file = topic_dir / "raw.json"

        if json_file.exists():
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            body_html = data.get('bodyHtml', '')

            # FIRST embed images (before we strip data-src attributes)
            processed_html = embed_images_in_html(body_html)
            # THEN clean up the HTML structure
            processed_html = process_source_html(processed_html)

            html_parts.append(f'    <div class="topic-section" id="{anchor}">\n')
            html_parts.append(f'        <h{header_level}>{label}</h{header_level}>\n')
            html_parts.append(f'        {processed_html}\n')
            html_parts.append('    </div>\n\n')

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(topics)} topics...")

    html_parts.append('    </div>\n')  # Close main-content
    html_parts.append('</body>\n</html>')

    html_content = ''.join(html_parts)
    HTML_FILE.write_text(html_content, encoding='utf-8')

    size_mb = HTML_FILE.stat().st_size / (1024 * 1024)
    print(f"\nCreated: {HTML_FILE}")
    print(f"Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    create_html()
