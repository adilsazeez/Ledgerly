
from rest_framework import serializers

class LinkTokenCreateSerializer(serializers.Serializer):
    user_id = serializers.CharField(required=False, help_text="Optional user ID for testing without auth")

class ExchangePublicTokenSerializer(serializers.Serializer):
    public_token = serializers.CharField(required=True, help_text="The public token returned by Plaid Link")
    user_id = serializers.CharField(required=False, help_text="Optional user ID for testing without auth")

class TestAuthResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    user_id = serializers.CharField()
    email = serializers.CharField()


class CreditScoreRequestSerializer(serializers.Serializer):
    user_id = serializers.CharField(required=False, help_text="Optional user ID for testing without auth")
    plaid_user_id = serializers.CharField(required=False, help_text="Optional Plaid user_id from /user/create")
