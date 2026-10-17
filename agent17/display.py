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
        for wrapped in group:
            if len(current) == capacity:
                chunks.append(current)
                current = []
            current.append(wrapped)
    if current:
        chunks.append(current)
    return ['\n'.join(chunk + [f'Trang {i+1}/{len(chunks)} | Tiếp / Trước'])
            for i, chunk in enumerate(chunks)]


def order_sections(information):
    """Order model-labeled groups for display; never infer/rewrite legal content."""
    from copy import deepcopy
    result=deepcopy(information)
    order={'prepare':0,'steps':0,'content':0,'conditional':1,'authority':2,'quantity':3,'notes':4,'gap':5}
    result['sections']=sorted(result.get('sections',[]),key=lambda s:order.get(s.get('kind','content'),0))
    return result
