from django.test import TestCase


class LlmsTxtTestCase(TestCase):
    def test_returns_200_with_plain_text(self):
        # Act
        response = self.client.get('/llms.txt')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')

    def test_contains_site_title_and_summary(self):
        # Act
        response = self.client.get('/llms.txt')

        # Assert
        content = response.content.decode()
        self.assertIn('# Ottawa Bicycle Club', content)
        self.assertIn('non-commercial', content)

    def test_contains_event_links(self):
        # Act
        response = self.client.get('/llms.txt')

        # Assert
        content = response.content.decode()
        self.assertIn('/upcoming', content)
        self.assertIn('/events.ics', content)

    def test_links_to_mcp_server_and_poppy_manifest(self):
        # Act
        response = self.client.get('/llms.txt')

        # Assert
        content = response.content.decode()
        self.assertIn('/mcp', content)
        self.assertIn('/.well-known/poppy.json', content)


class PoppyManifestTestCase(TestCase):
    def test_returns_json_for_protocol_version_one(self):
        # Act
        response = self.client.get('/.well-known/poppy.json')

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json()['protocol_version'], '1.0')

    def test_organization_domain_is_request_host(self):
        # Act
        response = self.client.get('/.well-known/poppy.json', HTTP_HOST='localhost')

        # Assert
        self.assertEqual(response.json()['organization'], {
            'name': 'Ottawa Bicycle Club',
            'domain': 'localhost',
        })

    def test_lists_mcp_api_on_same_host(self):
        # Act
        response = self.client.get('/.well-known/poppy.json', HTTP_HOST='localhost')

        # Assert
        manifest = response.json()
        self.assertEqual(manifest['apis'], [{
            'type': 'mcp',
            'url': 'https://localhost/mcp',
            'description': manifest['apis'][0]['description'],
        }])
        self.assertIn('web browser', manifest['apis'][0]['description'])

    def test_offers_website_without_sign_in(self):
        # Act
        manifest = self.client.get('/.well-known/poppy.json').json()

        # Assert
        self.assertEqual(manifest['web'], {})
        self.assertNotIn('auth', manifest)

    def test_is_publicly_cacheable(self):
        # Act
        response = self.client.get('/.well-known/poppy.json')

        # Assert
        self.assertIn('public', response['Cache-Control'])
        self.assertIn('max-age=3600', response['Cache-Control'])

    def test_rejects_post(self):
        # Act
        response = self.client.post('/.well-known/poppy.json')

        # Assert
        self.assertEqual(response.status_code, 405)

    def test_oauth_protected_resource_metadata_is_absent(self):
        # Act
        response = self.client.get('/.well-known/oauth-protected-resource')

        # Assert
        self.assertEqual(response.status_code, 404)
