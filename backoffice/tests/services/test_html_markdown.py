from django.test import TestCase

from backoffice.services.html_markdown import html_to_markdown


class HtmlToMarkdownTestCase(TestCase):
    def test_empty_input_returns_empty_string(self):
        # Act / Assert
        self.assertEqual(html_to_markdown(None), '')
        self.assertEqual(html_to_markdown(''), '')

    def test_paragraphs_are_separated_by_blank_lines(self):
        # Act
        result = html_to_markdown('<p>First</p><p>Second</p>')

        # Assert
        self.assertEqual(result, 'First\n\nSecond')

    def test_emphasis_and_links(self):
        # Act
        result = html_to_markdown('<p><strong>Bold</strong> and <em>italic</em> <a href="https://x.ca">link</a></p>')

        # Assert
        self.assertEqual(result, '**Bold** and _italic_ [link](https://x.ca)')

    def test_lists(self):
        # Act
        result = html_to_markdown('<ul><li>One</li><li>Two</li></ul><ol><li>First</li><li>Second</li></ol>')

        # Assert
        self.assertEqual(result, '- One\n- Two\n\n1. First\n2. Second')

    def test_headings_and_line_breaks(self):
        # Act
        result = html_to_markdown('<h2>Route</h2><p>Line one<br>Line two</p>')

        # Assert
        self.assertEqual(result, '## Route\n\nLine one\nLine two')

    def test_entities_are_decoded(self):
        # Act
        result = html_to_markdown('<p>Fish &amp; chips</p>')

        # Assert
        self.assertEqual(result, 'Fish & chips')
