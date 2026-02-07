
import os
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from supabase import create_client, Client
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from .plaid_init import get_plaid_client
# Import schema to register the authentication extension
from . import schema
from .serializers import LinkTokenCreateSerializer, ExchangePublicTokenSerializer, TestAuthResponseSerializer
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

@extend_schema(
    description="Test authentication endpoint. Returns user details from Supabase token.",
    responses={200: TestAuthResponseSerializer}
)
@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def test_auth(request):
    return Response({
        "message": "You are authenticated!",
        "user_id": request.user.username,
        "email": request.user.email
    })

@extend_schema(
    description="Create a Plaid Link Token.",
    request=LinkTokenCreateSerializer,
    responses={200: {"type": "object", "description": "Plaid Link Token response"}}
)
@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def create_link_token(request):
    try:
        client = get_plaid_client()

        # Get user_id from authenticated user OR request body (for testing)
        user_id = None
        if request.user.is_authenticated:
            user_id = request.user.username
        else:
            user_id = request.data.get('user_id')

        if not user_id:
             return Response({'error': 'User ID is required. Please authenticate or provide "user_id" in body.'}, status=status.HTTP_400_BAD_REQUEST)

        request_plaid = LinkTokenCreateRequest(
            products=[Products('transactions')],
            client_name="Ledgerly",
            country_codes=[CountryCode('US')],
            language='en',
            user=LinkTokenCreateRequestUser(
                client_user_id=user_id
            )
        )
        response = client.link_token_create(request_plaid)
        print(response)
        return Response(response.to_dict())
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description="Exchange Plaid Public Token for Access Token and store in Supabase.",
    request=ExchangePublicTokenSerializer,
    responses={200: {"type": "object", "properties": {"message": {"type": "string"}}}}
)
@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def exchange_public_token(request):
    public_token = request.data.get('public_token')
    if not public_token:
        return Response({'error': 'public_token is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client = get_plaid_client()
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=public_token
        )
        exchange_response = client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']
        
        # Store in Supabase
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)

        # Get user_id from authenticated user OR request body (for testing)
        user_id = None
        if request.user.is_authenticated:
            user_id = request.user.username
        else:
            user_id = request.data.get('user_id')

        if not user_id:
             return Response({'error': 'User ID is required. Please authenticate or provide "user_id" in body.'}, status=status.HTTP_400_BAD_REQUEST)
        
        data = {
            "user_id": user_id,
            "access_token": access_token,
            "item_id": item_id
        }
        
        # Insert into user_plaid_items table
        supabase.table("user_plaid_items").insert(data).execute()

        return Response({'message': 'Public token exchanged and saved successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest


# @api_view(['POST'])
# def simulate_on_success(request):
#     """
#     Simulates the frontend 'onSuccess' by generating a public_token
#     directly in the Sandbox environment.
#     """
#     try:
#         client = get_plaid_client()
#
#         # Use a standard Sandbox Institution ID (ins_109508 is First Platypus Bank)
#         pt_request = SandboxPublicTokenCreateRequest(
#             institution_id='ins_109508',
#             initial_products=[Products('transactions')]
#         )
#
#         # This skips the UI and gives you the public_token!
#         response = client.sandbox_public_token_create(pt_request)
#         return Response(response.to_dict())
#
#     except Exception as e:
#         return Response({'error': str(e)}, status=400)

@extend_schema(
    description="Check if user has connected to Plaid.",
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)")
    ],
    responses={200: {"type": "object", "properties": {"is_connected": {"type": "boolean"}}}}
)
@api_view(['GET'])
def check_plaid_status(request):
    # Get user_id from authenticated user OR query param (for testing)
    user_id = None
    if request.user.is_authenticated:
        user_id = request.user.username
    else:
        user_id = request.query_params.get('user_id')

    if not user_id:
         return Response({'error': 'User ID is required. Please authenticate or provide "user_id" in query params.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)
        
        response = supabase.table("user_plaid_items").select("*", count="exact").eq("user_id", user_id).execute()
        
        is_connected = False
        if response.count and response.count > 0:
            is_connected = True
            
        return Response({'is_connected': is_connected})

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
