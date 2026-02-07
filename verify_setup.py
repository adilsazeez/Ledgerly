
import os
import django
from django.conf import settings

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ledgerly.settings')
django.setup()

def check_setup():
    print("Checking setup...")
    
    # Check INSTALLED_APPS
    if 'rest_framework' not in settings.INSTALLED_APPS:
        print("FAIL: rest_framework not in INSTALLED_APPS")
    else:
        print("PASS: rest_framework is installed")

    # Check REST_FRAMEWORK settings
    rf = getattr(settings, 'REST_FRAMEWORK', {})
    auth_classes = rf.get('DEFAULT_AUTHENTICATION_CLASSES', [])
    if 'ledgerly_app.authentication.SupabaseAuthentication' in auth_classes:
        print("PASS: SupabaseAuthentication is configured")
    else:
        print(f"FAIL: SupabaseAuthentication missing from settings. Found: {auth_classes}")

    # Check Import
    try:
        from ledgerly_app.authentication import SupabaseAuthentication
        print("PASS: SupabaseAuthentication class importable")
    except ImportError as e:
        print(f"FAIL: Could not import SupabaseAuthentication: {e}")
    except Exception as e:
        print(f"FAIL: Error importing SupabaseAuthentication: {e}")

    # Check Plaid
    try:
        import plaid
        print("PASS: plaid-python is installed")
    except ImportError:
        print("FAIL: plaid-python is NOT installed")

    # Check Environment
    if not os.environ.get('SUPABASE_URL') or 'your-project' in os.environ.get('SUPABASE_URL', ''):
         print("WARN: SUPABASE_URL appears to be default/empty. Please update .env")
    else:
         print("PASS: SUPABASE_URL is set")

    if not os.environ.get('PLAID_CLIENT_ID') or 'your-plaid-client-id' in os.environ.get('PLAID_CLIENT_ID', ''):
        print("WARN: PLAID_CLIENT_ID appears to be default/empty. Please update .env")
    else:
        print("PASS: PLAID_CLIENT_ID is set")

if __name__ == "__main__":
    check_setup()
