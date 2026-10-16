"""Deterministic display pagination; never truncates source content."""
import textwrap
import unicodedata

def format_information(information):
    """Plain text for the existing Unity UI; never include internal node IDs."""
    blocks = []
    title = information.get('title', '').strip()
    if title:
        blocks.append(title)
    for section in information.get('sections', []):
        lines = []
        heading = section.get('title', '').strip()
        if heading:
            lines.append(heading)
        lines.extend('- ' + item.strip() for item in section.get('items', []) if item.strip())
        if lines:
            blocks.append('\n'.join(lines))
    options = []
    for option in information.get('options', []):
        label = option.get('label', '').strip()
        if label:
            identifier = option.get('id', '').strip()
            options.append(f'{identifier}. {label}' if identifier else label)
    if options:
        blocks.append('\n'.join(options))
    return '\n\n'.join(blocks)


def paginate(information, columns=40, rows=11):
    if columns < 24 or rows < 5:
        raise ValueError('Display requires at least 24 columns and 5 rows')
    text = unicodedata.normalize('NFC', format_information(information))
    if not text:
        return []
    capacity = rows - 1
    chunks, current = [], []
    for line in text.splitlines():
        group = textwrap.wrap(line, width=columns, replace_whitespace=False,
                              break_long_words=True, break_on_hyphens=False) or ['']
        if len(group) <= capacity and current and len(current) + len(group) > capacity:
            chunks.append(current)
            current = []
        for wrapped in group:
            if len(current) == capacity:
                chunks.append(current)
                current = []
            current.append(wrapped)
    if current:
        chunks.append(current)
    return ['\n'.join(chunk + [f'Trang {i+1}/{len(chunks)} | Tiếp / Trước'])
            for i, chunk in enumerate(chunks)]
