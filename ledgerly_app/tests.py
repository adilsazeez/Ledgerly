from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
import os

class WebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('ledgerly_app.views.get_plaid_client')
    def test_create_link_token_webhook_url(self, mock_get_plaid_client):
        # Mock Plaid client
        mock_client_instance = MagicMock()
        mock_get_plaid_client.return_value = mock_client_instance
        mock_client_instance.link_token_create.return_value.to_dict.return_value = {'link_token': 'test_token'}
        
        # Mock env var
        with patch.dict(os.environ, {'PLAID_WEBHOOK_URL': 'https://test-webhook.com'}):
            url = reverse('create_link_token')
            response = self.client.post(url, {'user_id': 'test_user'}, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Verify LinkTokenCreateRequest was called with correct webhook
            args, kwargs = mock_client_instance.link_token_create.call_args
            request_plaid = args[0]
            self.assertEqual(request_plaid.webhook, 'https://test-webhook.com')

    @patch('ledgerly_app.views.get_plaid_client')
    @patch('ledgerly_app.views.create_client')
    def test_handle_plaid_webhook(self, mock_create_client, mock_get_plaid_client):
        # Mock Supabase
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        # Mock select response with cursor
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{'access_token': 'test_access_token', 'cursor': 'old_cursor'}]
        
        # Mock Plaid
        mock_plaid_client = MagicMock()
        mock_get_plaid_client.return_value = mock_plaid_client
        mock_plaid_client.transactions_sync.return_value = {
            'added': [], 
            'modified': [], 
            'removed': [],
            'next_cursor': 'new_next_cursor'
        }
        
        url = reverse('plaid-webhook')
        data = {
            'webhook_type': 'TRANSACTIONS',
            'webhook_code': 'SYNC_UPDATES_AVAILABLE',
            'item_id': 'test_item_id'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify Supabase select
        mock_supabase.table.assert_any_call('user_plaid_items')
        mock_supabase.table().select.assert_called_with('access_token, cursor')
        mock_supabase.table().select().eq.assert_called_with('item_id', 'test_item_id')
        
        # Verify Plaid sync called with old cursor
        mock_plaid_client.transactions_sync.assert_called()
        args, _ = mock_plaid_client.transactions_sync.call_args
        self.assertEqual(args[0].cursor, 'old_cursor')
        
        # Verify Supabase update called with new cursor
        mock_supabase.table().update.assert_called_with({'cursor': 'new_next_cursor'})
        mock_supabase.table().update().eq.assert_called_with('item_id', 'test_item_id')

    @patch('ledgerly_app.views.get_plaid_client')
    @patch('ledgerly_app.views.create_client')
    def test_get_transactions_recurring(self, mock_create_client, mock_get_plaid_client):
        # Mock Supabase
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{'access_token': 'test_token', 'cursor': 'old_cursor'}]
        
        # Mock Plaid
        mock_plaid_client = MagicMock()
        mock_get_plaid_client.return_value = mock_plaid_client
        
        # Mock sync response
        mock_sync_response = MagicMock()
        mock_sync_response.to_dict.return_value = {
            'added': [], 'modified': [], 'removed': [], 'next_cursor': 'new_cursor'
        }
        mock_sync_response.__getitem__ = lambda s, k: 'new_cursor' if k == 'next_cursor' else None
        mock_plaid_client.transactions_sync.return_value = mock_sync_response
        
        # Mock recurring response
        mock_recurring_response = MagicMock()
        mock_recurring_response.to_dict.return_value = {
            'inflow_streams': [{'description': 'salary'}],
            'outflow_streams': [{'description': 'rent'}]
        }
        mock_plaid_client.transactions_recurring_get.return_value = mock_recurring_response
        
        # Authenticate user
        user = MagicMock()
        user.is_authenticated = True
        user.username = 'test_user'
        self.client.force_authenticate(user=user) # This might not work with standard APIClient if using custom auth, but let's try assuming standard DRF
        # Actually views.py uses request.user.username manually. Let's mock request.user
        
        # Since I can't easily mock request.user with standard APIClient without proper setup, 
        # I'll rely on the view logic: if user_id is in query params it works too (for testing)
        url = reverse('get_transactions')
        response = self.client.get(url, {'user_id': 'test_user'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('inflow_streams', data)
        self.assertIn('outflow_streams', data)
        self.assertEqual(data['inflow_streams'], [{'description': 'salary'}])
        self.assertEqual(data['outflow_streams'], [{'description': 'rent'}])
        
        # Verify calls
        mock_plaid_client.transactions_sync.assert_called()
        mock_plaid_client.transactions_recurring_get.assert_called()

    @patch('ledgerly_app.views.get_plaid_client')
    @patch('ledgerly_app.views.create_client')
    def test_refresh_transactions(self, mock_create_client, mock_get_plaid_client):
        # Mock Supabase
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{'access_token': 'test_token'}]
        
        # Mock Plaid
        mock_plaid_client = MagicMock()
        mock_get_plaid_client.return_value = mock_plaid_client
        mock_plaid_client.transactions_refresh.return_value.to_dict.return_value = {'request_id': 'test_req_id'}
        
        url = reverse('refresh_transactions')
        # Similar user_id handling as before
        response = self.client.post(url, {'user_id': 'test_user'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify Supabase call
        mock_supabase.table.assert_called_with('user_plaid_items')
        mock_supabase.table().select.assert_called_with('access_token')
        mock_supabase.table().select().eq.assert_called_with('user_id', 'test_user')
        
        # Verify Plaid refresh called
        mock_plaid_client.transactions_refresh.assert_called()
