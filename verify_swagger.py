
import os
import django
from django.conf import settings
from django.urls import reverse

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ledgerly.settings')
django.setup()

from drf_spectacular.generators import SchemaGenerator

def check_swagger():
    print("Checking Swagger Setup...")
    
    # Check INSTALLED_APPS
    if 'drf_spectacular' not in settings.INSTALLED_APPS:
        print("FAIL: drf_spectacular not in INSTALLED_APPS")
    else:
        print("PASS: drf_spectacular is installed")

    # Check REST_FRAMEWORK settings
    rf = getattr(settings, 'REST_FRAMEWORK', {})
    if rf.get('DEFAULT_SCHEMA_CLASS') == 'drf_spectacular.openapi.AutoSchema':
        print("PASS: DEFAULT_SCHEMA_CLASS is correct")
    else:
        print(f"FAIL: DEFAULT_SCHEMA_CLASS is {rf.get('DEFAULT_SCHEMA_CLASS')}")

    # Try generating schema
    try:
        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        if schema:
            print("PASS: Schema generated successfully")
        else:
            print("FAIL: Schema generation returned empty")
    except Exception as e:
        print(f"FAIL: Schema generation failed: {e}")

if __name__ == "__main__":
    check_swagger()
