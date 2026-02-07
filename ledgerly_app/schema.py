
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from .authentication import SupabaseAuthentication

class SupabaseAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = SupabaseAuthentication
    name = 'SupabaseAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
