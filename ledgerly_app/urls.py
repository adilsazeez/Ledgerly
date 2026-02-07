
from django.urls import path
from . import views

urlpatterns = [
    path('test-auth/', views.test_auth, name='test_auth'),
    path('create-link-token/', views.create_link_token, name='create_link_token'),
    path('exchange-public-token/', views.exchange_public_token, name='exchange_public_token'),
]
