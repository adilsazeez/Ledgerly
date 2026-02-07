
from django.urls import path
from . import views

urlpatterns = [
    path('test-auth/', views.test_auth, name='test_auth'),
    path('create-link-token/', views.create_link_token, name='create_link_token'),
    path('exchange-public-token/', views.exchange_public_token, name='exchange_public_token'),
    path('check-plaid-status/', views.check_plaid_status, name='check_plaid_status'),
    path('get-account-balance/', views.get_account_balance, name='get_accounts'),
    path('get-transactions/', views.get_transactions, name='get_transactions'),
    path('plaid-webhook/', views.handle_plaid_webhook, name='plaid-webhook'),
    path('refresh-transactions/', views.refresh_transactions, name='refresh_transactions'),
    path('connected-institutions/', views.get_connected_institutions, name='get_connected_institutions'),
]
