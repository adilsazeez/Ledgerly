
import os
import plaid
from plaid.api import plaid_api

def get_plaid_client():
    client_id = os.getenv('PLAID_CLIENT_ID')
    secret = os.getenv('PLAID_SECRET')
    environment = os.getenv('PLAID_ENV', 'sandbox')

    # Debug print: Remove this once it works!
    print(f"Loading Plaid with Client ID: {client_id}")



    if environment == 'sandbox':
        host = plaid.Environment.Sandbox
    elif environment == 'development':
        host = plaid.Environment.Development
    elif environment == 'production':
        host = plaid.Environment.Production
    else:
        host = plaid.Environment.Sandbox

    configuration = plaid.Configuration(
        host=host,
        api_key={
            'clientId': client_id,
            'secret': secret,
        }
    )
    api_client = plaid.ApiClient(configuration)
    client = plaid_api.PlaidApi(api_client)
    return client
