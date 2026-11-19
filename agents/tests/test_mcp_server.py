import json
from datetime import timedelta

from asgiref.sync import async_to_sync
from django.test import TestCase
from django.utils import timezone

from agents.mcp_server import build_mcp_app
from agents.middleware import AgentTrackingAsgiMiddleware
from agents.models import AgentRequest
from backoffice.models import Event, Program, Registration, Ride, Route

PROTOCOL_VERSION = '2025-06-18'


async def _send_request(app, body, headers):
    messages = [{'type': 'http.request', 'body': json.dumps(body).encode(), 'more_body': False}]
    response = {'status': None, 'headers': {}, 'body': b''}

    async def receive():
        if messages:
            return messages.pop(0)
        return {'type': 'http.disconnect'}

    async def send(message):
        if message['type'] == 'http.response.start':
            response['status'] = message['status']
            response['headers'] = {key.decode(): value.decode() for key, value in message.get('headers', [])}
        elif message['type'] == 'http.response.body':
            response['body'] += message.get('body', b'')

    scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': 'POST',
        'scheme': 'http',
        'path': '/mcp',
        'raw_path': b'/mcp',
        'query_string': b'',
        'root_path': '',
        'server': ('localhost', 8000),
        'client': ('127.0.0.1', 50000),
        'headers': [(key.lower().encode(), value.encode()) for key, value in headers.items()],
    }
    starlette_app = app.app if isinstance(app, AgentTrackingAsgiMiddleware) else app
    async with starlette_app.router.lifespan_context(starlette_app):
        await app(scope, receive, send)
    return response


class BaseMcpServerTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name='Social Rides')
        self.starts_at = (timezone.now() + timedelta(days=5)).replace(minute=0, second=0, microsecond=0)

    def _create_event(self, name='Sunday Ride', state=Event.STATE_LIVE):
        return Event.objects.create(
            program=self.program,
            name=name,
            state=state,
            description='<p>Coffee stop included.</p>',
            starts_at=self.starts_at,
            ends_at=self.starts_at + timedelta(hours=3),
            registration_closes_at=self.starts_at - timedelta(hours=1),
        )

    def _post(self, body, headers=None, app=None):
        request_headers = {
            'host': 'localhost:8000',
            'content-type': 'application/json',
            'accept': 'application/json, text/event-stream',
            'mcp-protocol-version': PROTOCOL_VERSION,
        }
        request_headers.update(headers or {})
        return async_to_sync(_send_request)(app or build_mcp_app(), body, request_headers)

    def _rpc(self, method, params=None, headers=None, app=None):
        body = {'jsonrpc': '2.0', 'id': 1, 'method': method}
        if params is not None:
            body['params'] = params
        response = self._post(body, headers, app)
        is_json = response['headers'].get('content-type', '').startswith('application/json')
        return response, json.loads(response['body']) if is_json else None

    def _call_tool(self, name, arguments):
        response, payload = self._rpc('tools/call', {'name': name, 'arguments': arguments})
        self.assertEqual(response['status'], 200)
        return payload['result']


class McpLifecycleTestCase(BaseMcpServerTestCase):
    def test_initialize_negotiates_protocol_and_returns_instructions(self):
        # Act
        response, payload = self._rpc('initialize', {
            'protocolVersion': PROTOCOL_VERSION,
            'capabilities': {},
            'clientInfo': {'name': 'test', 'version': '1'},
        })

        # Assert
        self.assertEqual(response['status'], 200)
        self.assertEqual(payload['result']['protocolVersion'], PROTOCOL_VERSION)
        self.assertEqual(payload['result']['serverInfo']['name'], 'Ottawa Bicycle Club rides')
        self.assertIn('web browser', payload['result']['instructions'])
        self.assertIn('tools', payload['result']['capabilities'])

    def test_lists_read_only_tools(self):
        # Act
        _, payload = self._rpc('tools/list')

        # Assert
        tools = {tool['name']: tool for tool in payload['result']['tools']}
        self.assertEqual(set(tools), {'fetch_events', 'fetch_event'})
        for tool in tools.values():
            self.assertTrue(tool['annotations']['readOnlyHint'])
            self.assertIn('web browser', tool['description'])
        self.assertEqual(tools['fetch_event']['inputSchema']['required'], ['event_id'])

    def test_rejects_foreign_origin(self):
        # Act
        response, _ = self._rpc('tools/list', headers={'origin': 'https://evil.example'})

        # Assert
        self.assertEqual(response['status'], 403)

    def test_rejects_unknown_host(self):
        # Act
        response, _ = self._rpc('tools/list', headers={'host': 'evil.example'})

        # Assert
        self.assertEqual(response['status'], 421)


class McpToolsTestCase(BaseMcpServerTestCase):
    def test_fetch_events_returns_structured_events_with_links(self):
        # Arrange
        event = self._create_event()
        self._create_event('Hidden Draft', state=Event.STATE_DRAFT)

        # Act
        result = self._call_tool('fetch_events', {})

        # Assert
        self.assertFalse(result['isError'])
        structured = result['structuredContent']
        self.assertEqual([item['id'] for item in structured['events']], [event.id])
        self.assertEqual(structured['events'][0]['url'], f'http://localhost:8000/events/{event.id}')
        self.assertIn('web browser', structured['advice'])
        self.assertEqual(json.loads(result['content'][0]['text']), structured)

    def test_fetch_events_reports_invalid_range_as_tool_error(self):
        # Act
        result = self._call_tool('fetch_events', {'start_date': '2027-02-01', 'end_date': '2027-01-01'})

        # Assert
        self.assertTrue(result['isError'])
        self.assertIn('end_date must be on or after start_date', result['content'][0]['text'])

    def test_fetch_events_rejects_malformed_date(self):
        # Act
        result = self._call_tool('fetch_events', {'start_date': 'next tuesday'})

        # Assert
        self.assertTrue(result['isError'])

    def test_fetch_event_returns_counts_without_names(self):
        # Arrange
        event = self._create_event()
        route = Route.objects.create(name='Loop', distance=60)
        ride = Ride.objects.create(name='B Ride', event=event, route=route)
        Registration.objects.create(event=event, ride=ride, name='Private Person', email='private@example.com',
                                    state=Registration.STATE_CONFIRMED)

        # Act
        result = self._call_tool('fetch_event', {'event_id': event.id})

        # Assert
        self.assertFalse(result['isError'])
        structured = result['structuredContent']
        self.assertEqual(structured['participants']['confirmed'], 1)
        self.assertEqual(structured['rides'][0]['participants'], 1)
        self.assertEqual(structured['registration']['url'], f'http://localhost:8000/events/{event.id}/registration')
        self.assertNotIn('Private Person', result['content'][0]['text'])
        self.assertNotIn('private@example.com', result['content'][0]['text'])

    def test_fetch_event_unknown_id_is_tool_error(self):
        # Act
        result = self._call_tool('fetch_event', {'event_id': 424242})

        # Assert
        self.assertTrue(result['isError'])
        self.assertIn('No event with id 424242', result['content'][0]['text'])

    def test_links_use_forwarded_scheme(self):
        # Arrange
        event = self._create_event()

        # Act
        _, payload = self._rpc('tools/call', {'name': 'fetch_event', 'arguments': {'event_id': event.id}},
                               headers={'x-forwarded-proto': 'https'})

        # Assert
        self.assertEqual(payload['result']['structuredContent']['url'], f'https://localhost:8000/events/{event.id}')


class McpTrackingTestCase(BaseMcpServerTestCase):
    def test_records_mcp_request_with_agent_family(self):
        # Arrange
        app = AgentTrackingAsgiMiddleware(build_mcp_app())

        # Act
        self._rpc('tools/list', headers={'user-agent': 'Claude-User/1.0'}, app=app)

        # Assert
        agent_request = AgentRequest.objects.get()
        self.assertEqual(agent_request.family, 'anthropic')
        self.assertEqual(agent_request.kind, AgentRequest.Kind.ASSISTANT)
        self.assertEqual(agent_request.path, '/mcp')
        self.assertEqual(agent_request.method, 'POST')
        self.assertEqual(agent_request.status_code, 200)
        self.assertTrue(agent_request.probe)

    def test_records_unknown_client_as_probe(self):
        # Arrange
        app = AgentTrackingAsgiMiddleware(build_mcp_app())

        # Act
        self._rpc('tools/list', headers={'user-agent': 'SomeClient/2.0'}, app=app)

        # Assert
        agent_request = AgentRequest.objects.get()
        self.assertEqual(agent_request.family, 'unknown')
        self.assertEqual(agent_request.kind, AgentRequest.Kind.PROBE)
