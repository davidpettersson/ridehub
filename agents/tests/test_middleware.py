from django.test import TestCase

from agents.models import AgentRequest

BROWSER_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/126.0.0.0 Safari/537.36'
)


class AgentTrackingMiddlewareTestCase(TestCase):
    def test_records_request_from_agent_user_agent(self):
        # Act
        self.client.get('/robots.txt', HTTP_USER_AGENT='Mozilla/5.0 (compatible; GPTBot/1.2)')

        # Assert
        agent_request = AgentRequest.objects.get()
        self.assertEqual(agent_request.family, 'openai')
        self.assertEqual(agent_request.kind, AgentRequest.Kind.CRAWLER)
        self.assertEqual(agent_request.path, '/robots.txt')
        self.assertEqual(agent_request.method, 'GET')
        self.assertEqual(agent_request.status_code, 200)
        self.assertFalse(agent_request.probe)
        self.assertFalse(agent_request.authenticated)

    def test_does_not_record_browser_traffic(self):
        # Act
        self.client.get('/robots.txt', HTTP_USER_AGENT=BROWSER_USER_AGENT)

        # Assert
        self.assertEqual(AgentRequest.objects.count(), 0)

    def test_records_probe_path_from_browser_user_agent(self):
        # Act
        self.client.get('/llms.txt', HTTP_USER_AGENT=BROWSER_USER_AGENT)

        # Assert
        agent_request = AgentRequest.objects.get()
        self.assertEqual(agent_request.family, 'unknown')
        self.assertEqual(agent_request.kind, AgentRequest.Kind.PROBE)
        self.assertTrue(agent_request.probe)

    def test_records_probe_path_from_agent_with_agent_classification(self):
        # Act
        self.client.get('/llms.txt', HTTP_USER_AGENT='Mozilla/5.0 (compatible; ClaudeBot/1.0)')

        # Assert
        agent_request = AgentRequest.objects.get()
        self.assertEqual(agent_request.family, 'anthropic')
        self.assertEqual(agent_request.kind, AgentRequest.Kind.CRAWLER)
        self.assertTrue(agent_request.probe)

    def test_records_status_code_for_missing_pages(self):
        # Act
        self.client.get('/does-not-exist', HTTP_USER_AGENT='python-requests/2.32.0')

        # Assert
        agent_request = AgentRequest.objects.get()
        self.assertEqual(agent_request.status_code, 404)
        self.assertEqual(agent_request.family, 'generic')

    def test_truncates_long_user_agent(self):
        # Act
        self.client.get('/robots.txt', HTTP_USER_AGENT='GPTBot/1.2 ' + 'x' * 600)

        # Assert
        agent_request = AgentRequest.objects.get()
        self.assertEqual(len(agent_request.user_agent), 512)
