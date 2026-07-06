from django.core.exceptions import ValidationError
from django.test import TestCase

from agents.models import AgentRequest


class AgentRequestTestCase(TestCase):
    def test_str_includes_family_method_and_path(self):
        # Arrange
        agent_request = AgentRequest.objects.create(
            family='anthropic',
            kind=AgentRequest.Kind.CRAWLER,
            user_agent='ClaudeBot/1.0',
            path='/upcoming',
            method='GET',
            status_code=200,
        )

        # Act
        result = str(agent_request)

        # Assert
        self.assertEqual(result, 'anthropic GET /upcoming')

    def test_invalid_kind_fails_validation(self):
        # Arrange
        agent_request = AgentRequest(
            family='anthropic',
            kind='invalid',
            user_agent='ClaudeBot/1.0',
            path='/upcoming',
            method='GET',
            status_code=200,
        )

        # Act / Assert
        with self.assertRaises(ValidationError):
            agent_request.full_clean()
