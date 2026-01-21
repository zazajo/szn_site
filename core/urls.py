from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.products, name='products'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),
    path('catalog/', views.catalog, name='catalog'),
    path('search/', views.search, name='search'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('payment-instructions/<str:order_number>/', views.payment_instructions, name='payment_instructions'),
    path('verify-payment/<str:order_number>/', views.verify_payment, name='verify_payment'),
    path('final-test/', views.final_email_test, name='final_test'),
]