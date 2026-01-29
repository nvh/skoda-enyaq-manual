#!/usr/bin/env python3
"""
Skoda Enyaq Manual Downloader
Downloads all topics from the digital manual and converts to markdown.
Also downloads all images locally.
"""

import json
import os
import re
import time
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from html.parser import HTMLParser

# Configuration
BASE_URL = "https://digital-manual.skoda-auto.com"
ROOT_TOPIC_ID = "c23949a70fa671f9ac14452546c7593f_3_nl_NL"
LANGUAGE = "nl_NL"
OUTPUT_DIR = Path("manual_output")
IMAGES_DIR = OUTPUT_DIR / "images"
COOKIES_FILE = Path("cookies.txt")

# Rate limiting
DELAY_BETWEEN_REQUESTS = 0.3  # seconds
IMAGE_DELAY = 0.1  # faster for images

# Global image cache to avoid re-downloading
downloaded_images = {}


class HTMLToMarkdown(HTMLParser):
    """Simple HTML to Markdown converter with image URL collection"""

    def __init__(self, topic_path=""):
        super().__init__()
        self.output = []
        self.list_stack = []
        self.in_code = False
        self.current_link = None
        self.skip_content = False
        self.image_urls = []  # Collect image URLs
        self.topic_path = topic_path

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'script' or tag == 'style':
            self.skip_content = True
            return

        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag[1])
            self.output.append('\n' + '#' * level + ' ')
        elif tag == 'p':
            self.output.append('\n\n')
        elif tag == 'br':
            self.output.append('\n')
        elif tag == 'strong' or tag == 'b':
            self.output.append('**')
        elif tag == 'em' or tag == 'i':
            self.output.append('*')
        elif tag == 'a':
            self.current_link = attrs_dict.get('href', '')
            self.output.append('[')
        elif tag == 'ul':
            self.list_stack.append('ul')
            self.output.append('\n')
        elif tag == 'ol':
            self.list_stack.append(('ol', 0))
            self.output.append('\n')
        elif tag == 'li':
            if self.list_stack:
                if self.list_stack[-1] == 'ul':
                    self.output.append('- ')
                else:
                    lst_type, num = self.list_stack[-1]
                    num += 1
                    self.list_stack[-1] = (lst_type, num)
                    self.output.append(f'{num}. ')
        elif tag == 'img':
            src = attrs_dict.get('data-src') or attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', 'image')
            if src:
                self.image_urls.append(src)
                # Placeholder - will be replaced after image download
                self.output.append(f'\n![{alt}]({{IMAGE:{src}}})\n')
        elif tag == 'code' or tag == 'pre':
            self.output.append('`')
            self.in_code = True
        elif tag == 'section':
            self.output.append('\n\n')
        elif tag == 'div':
            data_type = attrs_dict.get('data-type', '')
            if data_type in ['warning', 'note', 'caution']:
                self.output.append(f'\n\n> **{data_type.upper()}**: ')

    def handle_endtag(self, tag):
        if tag == 'script' or tag == 'style':
            self.skip_content = False
            return

        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.output.append('\n')
        elif tag == 'strong' or tag == 'b':
            self.output.append('**')
        elif tag == 'em' or tag == 'i':
            self.output.append('*')
        elif tag == 'a':
            if self.current_link:
                self.output.append(f']({self.current_link})')
            else:
                self.output.append('](#)')
            self.current_link = None
        elif tag == 'ul' or tag == 'ol':
            if self.list_stack:
                self.list_stack.pop()
            self.output.append('\n')
        elif tag == 'li':
            self.output.append('\n')
        elif tag == 'code' or tag == 'pre':
            self.output.append('`')
            self.in_code = False

    def handle_data(self, data):
        if self.skip_content:
            return
        if not self.in_code:
            data = re.sub(r'\s+', ' ', data)
        self.output.append(data)

    def get_markdown(self):
        result = ''.join(self.output)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()

    def get_image_urls(self):
        return self.image_urls


def url_to_filename(url):
    """Convert URL to a safe filename"""
    # Extract key parameter if present
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    if 'key' in params:
        key = params['key'][0]
        # Clean up the key to make a filename
        filename = re.sub(r'[^\w.-]', '_', key)
    else:
        # Use hash of URL for other cases
        filename = hashlib.md5(url.encode()).hexdigest()

    # Determine extension
    if '.svg' in url.lower():
        ext = '.svg'
    elif '.png' in url.lower():
        ext = '.png'
    elif '.jpg' in url.lower() or '.jpeg' in url.lower():
        ext = '.jpg'
    elif '.gif' in url.lower():
        ext = '.gif'
    else:
        ext = '.png'  # default

    if not filename.endswith(ext):
        filename += ext

    return filename


def download_image(url, cookies_str):
    """Download an image and return local path"""
    global downloaded_images

    if url in downloaded_images:
        return downloaded_images[url]

    try:
        filename = url_to_filename(url)
        local_path = IMAGES_DIR / filename

        # Check if already downloaded
        if local_path.exists():
            rel_path = f"images/{filename}"
            downloaded_images[url] = rel_path
            return rel_path

        # Download
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        req.add_header('Cookie', cookies_str)

        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()
            local_path.write_bytes(content)

        rel_path = f"images/{filename}"
        downloaded_images[url] = rel_path
        time.sleep(IMAGE_DELAY)
        return rel_path

    except Exception as e:
        print(f"\n  Warning: Failed to download image {url[:50]}...: {e}")
        downloaded_images[url] = url  # Fall back to original URL
        return url


def html_to_markdown(html_content, cookies_str, topic_path=""):
    """Convert HTML to Markdown and download images"""
    parser = HTMLToMarkdown(topic_path)
    try:
        parser.feed(html_content)
        markdown = parser.get_markdown()
        image_urls = parser.get_image_urls()

        # Download images and replace placeholders
        for img_url in image_urls:
            local_path = download_image(img_url, cookies_str)
            # Calculate relative path from topic to images
            depth = topic_path.count('/')
            rel_prefix = '../' * (depth + 1) if depth >= 0 else ''
            rel_path = rel_prefix + local_path
            markdown = markdown.replace(f'{{IMAGE:{img_url}}}', rel_path)

        return markdown
    except Exception as e:
        print(f"Warning: HTML parsing error: {e}")
        return re.sub(r'<[^>]+>', '', html_content)


def load_cookies():
    """Load cookies from file and return cookie string"""
    if not COOKIES_FILE.exists():
        raise FileNotFoundError(f"Cookies file not found: {COOKIES_FILE}")
    return COOKIES_FILE.read_text().strip()


def make_request(url, cookies_str):
    """Make HTTP request with cookies"""
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    req.add_header('Cookie', cookies_str)

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def fetch_topic_tree(cookies_str, topic_id):
    """Fetch the topic tree/TOC"""
    params = urllib.parse.urlencode({
        'key': topic_id,
        'displaytype': 'desktop',
        'language': LANGUAGE
    })
    url = f"{BASE_URL}/api/vw-topic/V1/topic?{params}"
    return make_request(url, cookies_str)


def fetch_topic_content(cookies_str, topic_id):
    """Fetch content for a specific topic"""
    params = urllib.parse.urlencode({
        'key': topic_id,
        'displaytype': 'topic',
        'language': LANGUAGE,
        'query': 'undefined'
    })
    url = f"{BASE_URL}/api/web/V6/topic?{params}"
    return make_request(url, cookies_str)


def extract_all_topics(tree_data, path=""):
    """Recursively extract all topics from the tree"""
    topics = []
    trees = tree_data.get('trees', [])
    for tree in trees:
        topics.extend(extract_topics_from_node(tree, path))
    return topics


def strip_html_tags(text):
    """Remove HTML tags from text, keeping only the text content"""
    if not text:
        return text
    # Remove HTML tags but keep their text content
    clean = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def extract_topics_from_node(node, path=""):
    """Extract topics from a tree node"""
    topics = []
    raw_label = node.get('label', 'Untitled')
    # Strip HTML tags from label
    label = strip_html_tags(raw_label)
    link_target = node.get('linkTarget')

    safe_label = re.sub(r'[^\w\s-]', '', label)[:50].strip()
    current_path = f"{path}/{safe_label}" if path else safe_label

    # Include all nodes - both with content (linkTarget) and category headers (no linkTarget)
    topics.append({
        'id': link_target,  # Will be None for category headers
        'label': label,
        'path': current_path,
        'is_category': link_target is None
    })

    for child in node.get('children', []):
        topics.extend(extract_topics_from_node(child, current_path))

    return topics


def sanitize_filename(name):
    """Create safe filename"""
    # First strip any HTML tags
    name = strip_html_tags(name)
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100]


def download_manual(resume_from=0):
    """Main download function"""
    print("Skoda Enyaq Manual Downloader")
    print("=" * 40)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading cookies...")
    cookies_str = load_cookies()

    print(f"Fetching topic tree from root: {ROOT_TOPIC_ID}...")
    tree_data = fetch_topic_tree(cookies_str, ROOT_TOPIC_ID)

    topics = extract_all_topics(tree_data)
    print(f"Found {len(topics)} topics to download")

    index_file = OUTPUT_DIR / "index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)
    print(f"Saved topic index to {index_file}")

    if resume_from > 0:
        print(f"Resuming from topic {resume_from}...")

    success_count = 0
    error_count = 0
    image_count = 0

    for i, topic in enumerate(topics):
        if i < resume_from:
            continue

        topic_id = topic['id']
        topic_path = topic['path']
        topic_label = topic['label']
        is_category = topic.get('is_category', False)

        print(f"[{i+1}/{len(topics)}] {topic_label[:40]}...", end=' ', flush=True)

        # Skip category headers (no content to download)
        if is_category or topic_id is None:
            print("(category)")
            continue

        try:
            content_data = fetch_topic_content(cookies_str, topic_id)
            body_html = content_data.get('bodyHtml', '')
            title = content_data.get('title', topic_label)

            prev_img_count = len(downloaded_images)
            markdown_content = html_to_markdown(body_html, cookies_str, topic_path)
            new_imgs = len(downloaded_images) - prev_img_count
            image_count += new_imgs

            full_markdown = f"# {title}\n\n{markdown_content}"

            topic_dir = OUTPUT_DIR / topic_path
            topic_dir.mkdir(parents=True, exist_ok=True)

            md_file = topic_dir / "content.md"
            md_file.write_text(full_markdown, encoding='utf-8')

            json_file = topic_dir / "raw.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(content_data, f, indent=2, ensure_ascii=False)

            img_info = f" (+{new_imgs} imgs)" if new_imgs > 0 else ""
            print(f"OK{img_info}")
            success_count += 1

        except Exception as e:
            print(f"ERROR: {e}")
            error_count += 1

        time.sleep(DELAY_BETWEEN_REQUESTS)

    print()
    print("=" * 40)
    print(f"Download complete!")
    print(f"Topics: {success_count} success, {error_count} errors")
    print(f"Images downloaded: {len(downloaded_images)}")
    print(f"Output: {OUTPUT_DIR.absolute()}")


def create_combined_markdown():
    """Create a single combined markdown file from all topics"""
    print("Creating combined markdown file...")

    index_file = OUTPUT_DIR / "index.json"
    if not index_file.exists():
        print("Run download first!")
        return

    with open(index_file, 'r', encoding='utf-8') as f:
        topics = json.load(f)

    combined = ["# Škoda Enyaq Handleiding\n\n"]
    combined.append("## Inhoudsopgave\n\n")

    for topic in topics:
        depth = topic['path'].count('/')
        indent = '  ' * depth
        anchor = sanitize_filename(topic['label'])
        combined.append(f"{indent}- [{topic['label']}](#{anchor})\n")

    combined.append("\n---\n\n")

    for topic in topics:
        topic_dir = OUTPUT_DIR / topic['path']
        md_file = topic_dir / "content.md"

        if md_file.exists():
            content = md_file.read_text(encoding='utf-8')
            # Fix image paths for combined file (all relative to root)
            content = re.sub(r'\.\./+images/', 'images/', content)
            anchor = sanitize_filename(topic['label'])
            combined.append(f"<a name=\"{anchor}\"></a>\n\n")
            combined.append(content)
            combined.append("\n\n---\n\n")

    combined_file = OUTPUT_DIR / "combined_manual.md"
    combined_file.write_text(''.join(combined), encoding='utf-8')
    print(f"Saved combined manual to {combined_file}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--combine':
        create_combined_markdown()
    elif len(sys.argv) > 1 and sys.argv[1] == '--resume':
        resume_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        download_manual(resume_from=resume_idx)
    else:
        download_manual()
        print()
        print("To create a single combined file, run:")
        print("  python3 download_manual.py --combine")
