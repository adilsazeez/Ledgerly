
import hashlib
import os
from datetime import date
from datetime import date

from plaid.model.credit_account_subtype import CreditAccountSubtype
from plaid.model.credit_account_subtypes import CreditAccountSubtypes
from plaid.model.credit_filter import CreditFilter
from plaid.model.depository_account_subtype import DepositoryAccountSubtype
from plaid.model.depository_account_subtypes import DepositoryAccountSubtypes
from plaid.model.depository_filter import DepositoryFilter
from plaid.model.link_token_account_filters import LinkTokenAccountFilters
from plaid.model.link_token_transactions import LinkTokenTransactions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from supabase import create_client, Client
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from .plaid_init import get_plaid_client
# Import schema to register the authentication extension
from . import schema
from .serializers import (
    LinkTokenCreateSerializer,
    ExchangePublicTokenSerializer,
    TestAuthResponseSerializer,
    CreditScoreRequestSerializer,
    SandboxTransactionCreateSerializer,
)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest
from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest
from plaid.model.transactions_refresh_request import TransactionsRefreshRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.user_create_request import UserCreateRequest
from plaid.model.cra_check_report_lend_score_get_request import CraCheckReportLendScoreGetRequest
from plaid.model.custom_sandbox_transaction import CustomSandboxTransaction
from plaid.model.sandbox_transactions_create_request import SandboxTransactionsCreateRequest

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
    description="Get Plaid CRA LendScore (credit score) for a user.",
    request=CreditScoreRequestSerializer,
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)"),
        OpenApiParameter("plaid_user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="Plaid user_id from /user/create (optional)"),
    ],
    responses={200: {"type": "object", "description": "Plaid LendScore response"}}
)
@api_view(['GET'])
def get_credit_score(request):
    user_id = request.user.username if request.user.is_authenticated else request.query_params.get('user_id')
    plaid_user_id = request.query_params.get('plaid_user_id')

    if not user_id and not plaid_user_id:
        return Response(
            {'error': 'User ID or plaid_user_id is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Mock credit score deterministically per user.
    basis = user_id or plaid_user_id
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    score = 600 + (int(digest[:8], 16) % 201)

    return Response({
        "user_id": user_id,
        "plaid_user_id": plaid_user_id,
        "credit_score": score,
        "source": "mock",
    })


@extend_schema(
    description="Get subscription payments for a user.",
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)"),
    ],
    responses={200: {"type": "array", "description": "Recurring subscription streams"}},
)
@api_view(['GET'])
def get_subscription_payments(request):
    user_id = request.user.username if request.user.is_authenticated else request.query_params.get('user_id')
    if not user_id:
        return Response(
            {'error': 'User ID is required. Please authenticate or provide "user_id" in query params.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)

        response = supabase.table("user_plaid_items").select("access_token").eq("user_id", user_id).execute()
        if not response.data or len(response.data) == 0:
            return Response({'error': 'No Plaid access token found for user'}, status=status.HTTP_404_NOT_FOUND)

        access_token = response.data[0]['access_token']
        client = get_plaid_client()
        request_plaid = TransactionsRecurringGetRequest(access_token=access_token)
        response_plaid = client.transactions_recurring_get(request_plaid)

        outflow_streams = response_plaid.to_dict().get('outflow_streams', [])

        def is_subscription(stream: dict) -> bool:
            primary = (stream.get('personal_finance_category_primary') or '').upper()
            detailed = (stream.get('personal_finance_category_detailed') or '').upper()
            description = (stream.get('description') or '').upper()
            merchant = (stream.get('merchant_name') or '').upper()
            return (
                'SUBSCRIPTION' in primary
                or 'SUBSCRIPTION' in detailed
                or 'SUBSCRIPTION' in description
                or 'SUBSCRIBE' in description
                or 'SUBSCRIPTION' in merchant
            )

        subscriptions = [s for s in outflow_streams if s.get('is_active') and is_subscription(s)]

        return Response(subscriptions)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Get upcoming payments for a user.",
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)"),
    ],
    responses={200: {"type": "array", "description": "Upcoming recurring payments"}},
)
@api_view(['GET'])
def get_upcoming_payments(request):
    user_id = request.user.username if request.user.is_authenticated else request.query_params.get('user_id')
    if not user_id:
        return Response(
            {'error': 'User ID is required. Please authenticate or provide "user_id" in query params.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)

        response = supabase.table("user_plaid_items").select("access_token").eq("user_id", user_id).execute()
        if not response.data or len(response.data) == 0:
            return Response({'error': 'No Plaid access token found for user'}, status=status.HTTP_404_NOT_FOUND)

        access_token = response.data[0]['access_token']
        client = get_plaid_client()
        request_plaid = TransactionsRecurringGetRequest(access_token=access_token)
        response_plaid = client.transactions_recurring_get(request_plaid)

        outflow_streams = response_plaid.to_dict().get('outflow_streams', [])

        upcoming = [
            s for s in outflow_streams
            if s.get('is_active') and s.get('predicted_next_date')
        ]

        def parse_predicted_date(value):
            if not value:
                return date.max
            if isinstance(value, date):
                return value
            if hasattr(value, "date"):
                return value.date()
            return date.fromisoformat(str(value))

        upcoming.sort(key=lambda s: parse_predicted_date(s.get('predicted_next_date')))

        return Response(upcoming)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Add a sandbox transaction for a user's Plaid item.",
    request=SandboxTransactionCreateSerializer,
    responses={200: {"type": "object", "description": "Sandbox transaction create response"}},
)
@api_view(['POST'])
def create_sandbox_transaction(request):
    user_id = request.user.username if request.user.is_authenticated else request.data.get('user_id')
    if not user_id:
        return Response(
            {'error': 'User ID is required. Please authenticate or provide "user_id" in body.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    amount = request.data.get('amount')
    description = request.data.get('description')
    date_transacted = request.data.get('date_transacted')
    date_posted = request.data.get('date_posted')
    iso_currency_code = request.data.get('iso_currency_code') or "USD"

    if amount is None or description is None:
        return Response(
            {'error': 'amount and description are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)

        response = supabase.table("user_plaid_items").select("access_token").eq("user_id", user_id).execute()
        if not response.data or len(response.data) == 0:
            return Response({'error': 'No Plaid access token found for user'}, status=status.HTTP_404_NOT_FOUND)

        access_token = response.data[0]['access_token']
        client = get_plaid_client()

        tx = CustomSandboxTransaction(
            date_transacted=date.fromisoformat(date_transacted) if date_transacted else date.today(),
            date_posted=date.fromisoformat(date_posted) if date_posted else date.today(),
            amount=float(amount),
            description=str(description),
            iso_currency_code=str(iso_currency_code),
        )

        create_request = SandboxTransactionsCreateRequest(
            access_token=access_token,
            transactions=[tx],
        )
        create_response = client.sandbox_transactions_create(create_request)
        return Response(create_response.to_dict())
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description="Create a Plaid Link Token.",
    request=LinkTokenCreateSerializer,
    responses={200: {"type": "object", "description": "Plaid Link Token response"}}
)
@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def create_link_token(request):
    try:
        print(request.data)
        client = get_plaid_client()
        print(request.data)

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
            transactions=LinkTokenTransactions(
                days_requested=90 # PAST 3 MONTHS
            ),
            client_name="Ledgerly",
            country_codes=[CountryCode('US')],
            language='en',
            user=LinkTokenCreateRequestUser(
                client_user_id=user_id
            ),
            account_filters=LinkTokenAccountFilters(
                depository=DepositoryFilter(
                    account_subtypes=DepositoryAccountSubtypes([
                        DepositoryAccountSubtype('checking'),
                        DepositoryAccountSubtype('savings')
                    ])
                ),
                credit=CreditFilter(
                    account_subtypes=CreditAccountSubtypes([
                        CreditAccountSubtype('credit card')
                    ])
                )
            ),
            webhook=os.environ.get('PLAID_WEBHOOK_URL', 'https://sample-web-hook.com')
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
    institution_id = request.data.get('institution_id')
    if not public_token:
        return Response({'error': 'public_token is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not institution_id:
        return Response({'error': 'institution_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Check if user already has an item with this institution
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

        # check duplicate institution
        existing = supabase.table("user_plaid_items").select("*").eq("user_id", user_id).eq("institution_id", institution_id).execute()
        if existing.data and len(existing.data) > 0:
             return Response({'message': 'Institution already linked'}, status=status.HTTP_200_OK)

        client = get_plaid_client()
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=public_token
        )
        exchange_response = client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']

        data = {
            "user_id": user_id,
            "access_token": access_token,
            "item_id": item_id,
            "institution_id": institution_id
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

@extend_schema(
    description="Get accounts from Plaid.",
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)")
    ],
    responses={200: {"type": "object", "description": "Plaid accounts response"}}
)
@api_view(['GET'])
def get_account_balance(request):
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

        # Get access token from Supabase
        response = supabase.table("user_plaid_items").select("access_token").eq("user_id", user_id).execute()

        if not response.data or len(response.data) == 0:
            return Response({'error': 'No Plaid access token found for user'}, status=status.HTTP_404_NOT_FOUND)

        access_token = response.data[0]['access_token']

        client = get_plaid_client()
        request_plaid = AccountsBalanceGetRequest(access_token=access_token)
        response_plaid = client.accounts_balance_get(request_plaid)

        return Response(response_plaid.to_dict())

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description="Get transactions from Plaid.",
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)"),
        OpenApiParameter("cursor", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="Cursor for pagination (optional)")
    ],
    responses={200: {"type": "object", "description": "Plaid transactions response"}}
)
@api_view(['GET'])
def get_transactions(request):
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

        # Get access token from Supabase
        # Get access token and cursor from Supabase
        response = supabase.table("user_plaid_items").select("access_token, cursor").eq("user_id", user_id).execute()

        if not response.data or len(response.data) == 0:
            return Response({'error': 'No Plaid access token found for user'}, status=status.HTTP_404_NOT_FOUND)

        access_token = response.data[0]['access_token']
        stored_cursor = response.data[0].get('cursor')

        # Use provided cursor or fallback to stored cursor
        cursor = request.query_params.get('cursor')
        if not cursor:
            cursor = stored_cursor

        client = get_plaid_client()
        request_plaid = TransactionsSyncRequest(
            access_token=access_token,
            cursor=cursor if cursor else None,
            count=500 # Adjust count as needed
        )
        response_plaid = client.transactions_sync(request_plaid)

        # Update cursor in DB if it changed
        next_cursor = response_plaid['next_cursor']
        if next_cursor != stored_cursor:
             supabase.table("user_plaid_items").update({"cursor": next_cursor}).eq("user_id", user_id).execute()

        # Fetch recurring transactions
        request_recurring = TransactionsRecurringGetRequest(
            access_token=access_token
        )
        response_recurring = client.transactions_recurring_get(request_recurring)

        result = response_plaid.to_dict()
        result['inflow_streams'] = response_recurring.to_dict().get('inflow_streams', [])
        result['outflow_streams'] = response_recurring.to_dict().get('outflow_streams', [])

        return Response(result)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description="Handle Plaid Webhooks.",
    request={"type": "object"},
    responses={200: {"type": "object", "properties": {"status": {"type": "string"}}}}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def handle_plaid_webhook(request):
    try:
        data = request.data
        webhook_type = data.get('webhook_type')
        webhook_code = data.get('webhook_code')
        item_id = data.get('item_id')

        print(f"Received webhook: type={webhook_type}, code={webhook_code}, item_id={item_id}")

        if webhook_type == 'TRANSACTIONS':
            # codes: SYNC_UPDATES_AVAILABLE, INITIAL_UPDATE, HISTORICAL_UPDATE, DEFAULT_UPDATE
            if webhook_code in ['SYNC_UPDATES_AVAILABLE', 'INITIAL_UPDATE', 'HISTORICAL_UPDATE', 'DEFAULT_UPDATE']:
                # Trigger transaction sync
                url = os.environ.get("SUPABASE_URL")
                key = os.environ.get("SUPABASE_KEY")
                supabase = create_client(url, key)

                # Get access token and cursor from Supabase
                response = supabase.table("user_plaid_items").select("access_token, cursor").eq("item_id", item_id).execute()

                if response.data and len(response.data) > 0:
                    access_token = response.data[0]['access_token']
                    cursor = response.data[0].get('cursor')

                    client = get_plaid_client()

                    request_plaid = TransactionsSyncRequest(
                        access_token=access_token,
                        cursor=cursor,
                        count=500
                    )
                    response_plaid = client.transactions_sync(request_plaid)

                    # Update cursor in DB
                    next_cursor = response_plaid['next_cursor']
                    supabase.table("user_plaid_items").update({"cursor": next_cursor}).eq("item_id", item_id).execute()

                    # Verification: just print for now
                    print(f"Synced {len(response_plaid['added'])} transactions, {len(response_plaid['modified'])} modified, {len(response_plaid['removed'])} removed.")
                else:
                    print(f"No access token found for item_id {item_id}")

        return Response({'status': 'received'}, status=status.HTTP_200_OK)
    except Exception as e:
        print(f"Error handling webhook: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description="Manually trigger a refresh of transactions.",
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)")
    ],
    responses={200: {"type": "object", "description": "Plaid transactions refresh response"}}
)
@api_view(['POST'])
def refresh_transactions(request):
    # Get user_id from authenticated user OR query param (for testing)
    user_id = None
    if request.user.is_authenticated:
        user_id = request.user.username
    else:
        user_id = request.data.get('user_id')

    if not user_id:
         return Response({'error': 'User ID is required. Please authenticate or provide "user_id" in body.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)

        # Get access token from Supabase
        response = supabase.table("user_plaid_items").select("access_token").eq("user_id", user_id).execute()

        if not response.data or len(response.data) == 0:
            return Response({'error': 'No Plaid access token found for user'}, status=status.HTTP_404_NOT_FOUND)

        access_token = response.data[0]['access_token']

        client = get_plaid_client()
        request_plaid = TransactionsRefreshRequest(access_token=access_token)
        response_plaid = client.transactions_refresh(request_plaid)

        return Response(response_plaid.to_dict())

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    description="Get connected institutions for the user.",
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, location=OpenApiParameter.QUERY, description="User ID (optional, for testing)")
    ],
    responses={200: {"type": "array", "items": {"type": "object", "properties": {
        "institution_name": {"type": "string"},
        "institution_id": {"type": "string"},
        "is_connected": {"type": "boolean"}
    }}}}
)
@api_view(['GET'])
def get_connected_institutions(request):
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
        
        # Get all items for user
        response = supabase.table("user_plaid_items").select("institution_id").eq("user_id", user_id).execute()
        
        connected_institutions = []
        client = get_plaid_client()

        if response.data:
            for item in response.data:
                institution_id = item.get('institution_id')
                if institution_id:
                    try:
                        request_plaid = InstitutionsGetByIdRequest(
                            institution_id=institution_id,
                            country_codes=[CountryCode('US')]
                        )
                        response_plaid = client.institutions_get_by_id(request_plaid)
                        institution = response_plaid['institution']
                        
                        connected_institutions.append({
                            "institution_name": institution.name,
                            "institution_id": institution.institution_id,
                            "is_connected": True
                        })
                    except Exception as e:
                        print(f"Error fetching institution details for {institution_id}: {e}")
                        # Optionally handle error, maybe still return ID
                        connected_institutions.append({
                            "institution_name": "Unknown Institution",
                            "institution_id": institution_id,
                            "is_connected": True,
                            "error": str(e)
                        })
        
        return Response(connected_institutions)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
