from django.test import TestCase

from agents.models import AgentRequest
from agents.services import AgentDetectionService


class AgentDetectionServiceTestCase(TestCase):
    def setUp(self):
        self.service = AgentDetectionService()

    def test_detects_claudebot_as_anthropic_crawler(self):
        # Act
        match = self.service.detect('Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)')

        # Assert
        self.assertEqual(match.family, 'anthropic')
        self.assertEqual(match.kind, AgentRequest.Kind.CRAWLER)

    def test_detects_claude_user_as_anthropic_assistant(self):
        # Act
        match = self.service.detect('Mozilla/5.0 (compatible; Claude-User/1.0; +Claude-User@anthropic.com)')

        # Assert
        self.assertEqual(match.family, 'anthropic')
        self.assertEqual(match.kind, AgentRequest.Kind.ASSISTANT)

    def test_detects_chatgpt_user_as_openai_assistant(self):
        # Act
        match = self.service.detect('Mozilla/5.0 AppleWebKit/537.36 (compatible; ChatGPT-User/1.0)')

        # Assert
        self.assertEqual(match.family, 'openai')
        self.assertEqual(match.kind, AgentRequest.Kind.ASSISTANT)

    def test_detects_gptbot_as_openai_crawler(self):
        # Act
        match = self.service.detect('Mozilla/5.0 AppleWebKit/537.36 (compatible; GPTBot/1.2)')

        # Assert
        self.assertEqual(match.family, 'openai')
        self.assertEqual(match.kind, AgentRequest.Kind.CRAWLER)

    def test_detects_perplexity_user_as_perplexity_assistant(self):
        # Act
        match = self.service.detect('Mozilla/5.0 (compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)')

        # Assert
        self.assertEqual(match.family, 'perplexity')
        self.assertEqual(match.kind, AgentRequest.Kind.ASSISTANT)

    def test_detection_is_case_insensitive(self):
        # Act
        match = self.service.detect('CLAUDEBOT/1.0')

        # Assert
        self.assertEqual(match.family, 'anthropic')

    def test_detects_python_requests_as_generic_script(self):
        # Act
        match = self.service.detect('python-requests/2.32.0')

        # Assert
        self.assertEqual(match.family, 'generic')
        self.assertEqual(match.kind, AgentRequest.Kind.SCRIPT)

    def test_detects_curl_as_generic_script(self):
        # Act
        match = self.service.detect('curl/8.5.0')

        # Assert
        self.assertEqual(match.family, 'generic')
        self.assertEqual(match.kind, AgentRequest.Kind.SCRIPT)

    def test_returns_none_for_browser_user_agent(self):
        # Act
        match = self.service.detect(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/126.0.0.0 Safari/537.36'
        )

        # Assert
        self.assertIsNone(match)

    def test_returns_none_for_missing_user_agent(self):
        # Act / Assert
        self.assertIsNone(self.service.detect(None))
        self.assertIsNone(self.service.detect(''))

    def test_llms_txt_is_probe_path(self):
        # Act / Assert
        self.assertTrue(self.service.is_probe_path('/llms.txt'))
        self.assertTrue(self.service.is_probe_path('/llms-full.txt'))

    def test_regular_paths_are_not_probe_paths(self):
        # Act / Assert
        self.assertFalse(self.service.is_probe_path('/upcoming'))
        self.assertFalse(self.service.is_probe_path('/robots.txt'))
