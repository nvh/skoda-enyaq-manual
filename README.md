# Škoda Enyaq Manual

Offline HTML version of the Škoda Enyaq digital manual with all images embedded.

## View Online

[**View the manual →**](https://nvh.github.io/skoda-enyaq-manual/)

## Features

- Single HTML file with all content and images embedded
- Sidebar navigation on wide screens
- Sticky stacked headers showing current section hierarchy
- Responsive design for mobile devices
- Works offline once loaded

## Scripts

### download_manual.py

Downloads all topics and images from the Škoda digital manual API.

```bash
# Requires cookies.txt with valid session cookies
python3 download_manual.py

# Create combined markdown file
python3 download_manual.py --combine
```

### create_html.py

Generates single HTML file from downloaded content.

```bash
python3 create_html.py
# Output: manual_output/manual.html
```

## License

Content © Škoda Auto. This repo only provides tools to create an offline copy for personal use.
