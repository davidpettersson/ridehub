import re
from html.parser import HTMLParser

BLOCK_TAGS = {'p', 'div', 'section', 'article', 'blockquote', 'ul', 'ol', 'table', 'tr'}
HEADING_TAGS = {'h1': '#', 'h2': '##', 'h3': '###', 'h4': '####', 'h5': '#####', 'h6': '######'}
EMPHASIS_TAGS = {'strong': '**', 'b': '**', 'em': '_', 'i': '_'}


class _MarkdownBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.list_stack: list[dict] = []
        self.link_stack: list[str | None] = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS or tag in HEADING_TAGS:
            self.parts.append('\n\n')
        if tag in HEADING_TAGS:
            self.parts.append(f'{HEADING_TAGS[tag]} ')
        elif tag in EMPHASIS_TAGS:
            self.parts.append(EMPHASIS_TAGS[tag])
        elif tag == 'br':
            self.parts.append('\n')
        elif tag in ('ul', 'ol'):
            self.list_stack.append({'ordered': tag == 'ol', 'index': 0})
        elif tag == 'li':
            self._start_list_item()
        elif tag == 'a':
            href = dict(attrs).get('href')
            self.link_stack.append(href)
            if href:
                self.parts.append('[')

    def handle_endtag(self, tag):
        if tag in EMPHASIS_TAGS:
            self.parts.append(EMPHASIS_TAGS[tag])
        elif tag in ('ul', 'ol') and self.list_stack:
            self.list_stack.pop()
        elif tag == 'a' and self.link_stack:
            href = self.link_stack.pop()
            if href:
                self.parts.append(f']({href})')
        if tag in BLOCK_TAGS or tag in HEADING_TAGS:
            self.parts.append('\n\n')

    def handle_data(self, data):
        self.parts.append(re.sub(r'\s+', ' ', data))

    def _start_list_item(self):
        self.parts.append('\n')
        if not self.list_stack:
            self.parts.append('- ')
            return
        current = self.list_stack[-1]
        current['index'] += 1
        indent = '  ' * (len(self.list_stack) - 1)
        marker = f"{current['index']}." if current['ordered'] else '-'
        self.parts.append(f'{indent}{marker} ')

    def markdown(self) -> str:
        text = ''.join(self.parts)
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n[ \t]+(?=[^\s\-\d])', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def html_to_markdown(html: str | None) -> str:
    if not html:
        return ''
    builder = _MarkdownBuilder()
    builder.feed(html)
    builder.close()
    return builder.markdown()
