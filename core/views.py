from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from .models import Product, Category, Cart, CartItem
from .forms import SearchForm
import uuid
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string
from .models import Order, OrderItem
from .forms import CheckoutForm, PaymentVerificationForm
import threading
from django.http import HttpResponse
import requests
import json
import os

# ==================== CONFIGURATION ====================
# CHANGE ADMIN EMAIL HERE
ADMIN_EMAIL = "josephedward201@gmail.com" 

def get_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            request.session.save() # Ensure session is saved
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart

def home(request):
    brand_images = [
        'images/b1.JPG',
        'images/b2.JPG', 
        'images/b3.JPG',
        'images/b4.JPG',
        'images/b5.JPG',
        'images/b6.JPG',
    ]
    
    featured_products = Product.objects.filter(featured=True, stock_quantity__gt=0)[:4]
    
    context = {
        'brand_images': brand_images,
        'featured_products': featured_products,
        'search_form': SearchForm()
    }
    return render(request, 'home.html', context)

def products(request):
    category_slug = request.GET.get('category')
    products_list = Product.objects.all()
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products_list = products_list.filter(category=category)
    
    categories = Category.objects.all()
    
    context = {
        'products': products_list,
        'categories': categories,
        'selected_category': category_slug,
        'search_form': SearchForm()
    }
    return render(request, 'products.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related_products = Product.objects.filter(
        category=product.category
    ).exclude(id=product.id)[:4]
    
    context = {
        'product': product,
        'related_products': related_products,
        'search_form': SearchForm()
    }
    return render(request, 'product_detail.html', context)

def catalog(request):
    categories = Category.objects.all()
    products_list = Product.objects.all()
    
    context = {
        'categories': categories,
        'products': products_list,
        'search_form': SearchForm()
    }
    return render(request, 'catalog.html', context)

def search(request):
    form = SearchForm(request.GET)
    results = []
    
    if form.is_valid() and form.cleaned_data['query']:
        query = form.cleaned_data['query']
        results = Product.objects.filter(
            Q(name__icontains=query) | 
            Q(category__name__icontains=query)
        )
    
    context = {
        'search_form': form,
        'results': results,
        'query': form.cleaned_data.get('query', '')
    }
    return render(request, 'search_results.html', context)

def cart(request):
    cart = get_cart(request)
    cart_items = CartItem.objects.filter(cart=cart)
    total = sum(item.total_price() for item in cart_items)
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'search_form': SearchForm()
    }
    return render(request, 'cart.html', context)

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if product.stock_quantity <= 0:
        messages.error(request, f"Sorry, {product.name} is out of stock.")
        return redirect('products')

    cart = get_cart(request)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )

    if not created:
        if cart_item.quantity + 1 > product.stock_quantity:
            messages.error(request, f"Only {product.stock_quantity} items of {product.name} available.")
            return redirect('cart')
        cart_item.quantity += 1
        cart_item.save()
    else:
        if cart_item.quantity > product.stock_quantity:
            messages.error(request, f"Only {product.stock_quantity} items of {product.name} available.")
            cart_item.delete()
            return redirect('cart')

    messages.success(request, f"Added {product.name} to cart.")
    return redirect('cart')

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f"{product_name} removed from cart.")
    return redirect('cart')

def update_cart(request, item_id):
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        cart_item = get_object_or_404(CartItem, id=item_id)
        
        if quantity > cart_item.product.stock_quantity:
            messages.error(request, f"Only {cart_item.product.stock_quantity} items available.")
            return redirect('cart')
        
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, "Cart updated.")
        else:
            cart_item.delete()
            messages.success(request, "Item removed from cart.")
    
    return redirect('cart')

def generate_order_number():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# ==================== EMAIL FUNCTIONS ====================

def send_resend_email(to_email, subject, text_content, html_content=None):
    """
    Send email via Resend API
    """
    api_key = os.environ.get('RESEND_API_KEY')
    if not api_key:
        print("❌ RESEND_API_KEY not set")
        return False, "API key not set"
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    data = {
        "from": "SZN IS REAL <noreply@sznisreal.com>",
        "to": [to_email],
        "subject": subject,
        "text": text_content,
    }
    
    if html_content:
        data["html"] = html_content
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return True, "Email sent"
        else:
            error_msg = f"Error {response.status_code}"
            try:
                error_data = response.json()
                error_msg += f": {error_data.get('message', 'Unknown error')}"
            except:
                error_msg += f": {response.text[:100]}"
            return False, error_msg
            
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, f"Error: {type(e).__name__}: {str(e)}"

def send_order_confirmation(order, cart_items):
    """
    Send order confirmation emails via Resend API
    """
    try:
        # Remove the "(Size: {item.size})" part since size is now in Order, not CartItem
        items_text = "\n".join([f"- {item.product.name} (Qty: {item.quantity}) - ₦{item.total_price()}" 
                               for item in cart_items])
        
        # 1. Email to ADMIN
        admin_subject = f'💰 New Order: {order.order_number}'
        admin_message = f"""
🛒 NEW ORDER RECEIVED

Order #: {order.order_number}
Customer: {order.customer_name}
Email: {order.customer_email}
Phone: {order.customer_phone}
Size: {order.customer_size if order.customer_size else 'Not specified'}
Address: {order.customer_address}, {order.city}, {order.state}

📦 ITEMS ORDERED:
{items_text}

💵 TOTAL: ₦{order.total_amount}

⏰ PAYMENT DEADLINE: {order.payment_deadline.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        print(f"\n📧 SENDING ADMIN EMAIL FOR ORDER {order.order_number}")
        success, msg = send_resend_email(
            ADMIN_EMAIL,  # Using the config variable
            admin_subject,
            admin_message
        )
        
        if success:
            print(f"✅ Admin email sent")
        else:
            print(f"❌ Admin email failed: {msg}")
        
        # 2. Email to CUSTOMER
        customer_subject = f'✅ Order Confirmation: #{order.order_number}'
        customer_message = f"""
Hi {order.customer_name},

Thank you for your order with SZN IS REAL! 🎉

📋 ORDER SUMMARY:
Order #: {order.order_number}
{items_text}
Size: {order.customer_size if order.customer_size else 'Not specified'}

💰 TOTAL: ₦{order.total_amount}

⏰ PAYMENT INSTRUCTIONS:
Please make payment within 2 hours to secure your order.
Payment details have been sent to our admin who will contact you shortly.

📞 CONTACT:
If you have questions, reply to this email or contact us.

Thank you for shopping with us!
SZN IS REAL Team
"""
        
        print(f"\n📧 SENDING CUSTOMER EMAIL FOR ORDER {order.order_number}")
        success, msg = send_resend_email(
            order.customer_email,
            customer_subject,
            customer_message
        )
        
        if success:
            print(f"✅ Customer email sent")
        else:
            print(f"❌ Customer email failed: {msg}")
            
    except Exception as e:
        print(f"🔥 Error sending order confirmation emails: {e}")
        import traceback
        traceback.print_exc()

def send_payment_verification(order, customer_name):
    """Send payment verification email"""
    try:
        subject = f'💳 Payment Verification - Order #{order.order_number}'
        
        message = f"""
💰 PAYMENT VERIFICATION RECEIVED

Order #: {order.order_number}
Customer: {customer_name}
Email: {order.customer_email}
Phone: {order.customer_phone}
Size: {order.customer_size if order.customer_size else 'Not specified'}

⚠️ Customer claims to have made payment. Please verify:

1. Check bank transfer
2. Confirm amount: ₦{order.total_amount}
3. Update order status to "Paid"

Items: {', '.join([item.product.name for item in order.orderitem_set.all()])}

Once verified, contact customer and update order status.
"""
        
        print(f"\n📧 SENDING PAYMENT VERIFICATION FOR ORDER {order.order_number}")
        success, msg = send_resend_email(
            ADMIN_EMAIL,
            subject,
            message
        )
        
        if success:
            print(f"✅ Payment verification sent")
        else:
            print(f"❌ Payment verification failed: {msg}")
            
    except Exception as e:
        print(f"Payment verification error: {e}")

# ==================== VIEWS ====================

def checkout(request):
    cart = get_cart(request)
    cart_items = CartItem.objects.filter(cart=cart)
    
    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect('cart')
    
    total = sum(item.total_price() for item in cart_items)
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Create order
            order = form.save(commit=False)
            order.order_number = generate_order_number()
            order.total_amount = total
            order.payment_deadline = timezone.now() + timedelta(hours=2)
            order.save()
            
            # Create order items
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price
                )
            
            # Send confirmation emails
            send_order_confirmation(order, cart_items)
            
            # Clear the cart
            cart_items.delete()
            
            messages.success(request, f"Order #{order.order_number} placed successfully! Check your email.")
            return redirect('payment_instructions', order_number=order.order_number)
    else:
        form = CheckoutForm()
    
    context = {
        'form': form,
        'total': total,
        'cart_items': cart_items,
        'search_form': SearchForm()
    }
    return render(request, 'checkout.html', context)

def payment_instructions(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    
    now = timezone.now()
    time_remaining = order.payment_deadline - now
    hours_remaining = max(0, int(time_remaining.total_seconds() // 3600))
    minutes_remaining = max(0, int((time_remaining.total_seconds() % 3600) // 60))
    
    context = {
        'order': order,
        'hours_remaining': hours_remaining,
        'minutes_remaining': minutes_remaining,
        'search_form': SearchForm()
    }
    return render(request, 'payment_instructions.html', context)

def verify_payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    
    if request.method == 'POST':
        form = PaymentVerificationForm(request.POST)
        if form.is_valid():
            customer_name = form.cleaned_data['customer_name']
            
            # ✅ CORRECTED: Use send_payment_verification (not send_payment_verification_email_async)
            send_payment_verification(order, customer_name)
            
            # Update order status
            order.status = 'paid'
            order.save()
            
            messages.success(request, "Payment verification received. We'll confirm your payment and process your order.")
            return redirect('home')
    else:
        form = PaymentVerificationForm()
    
    context = {
        'order': order,
        'form': form,
        'search_form': SearchForm()
    }
    return render(request, 'verify_payment.html', context)

# ==================== TEST ENDPOINTS ====================

def final_email_test(request):
    """Test complete email flow"""
    import time
    
    results = []
    results.append("<h1>🎯 Final Email System Test</h1>")
    
    results.append("<h2>Test 1: Admin Email</h2>")
    success, msg = send_resend_email(
        ADMIN_EMAIL,
        "Final Test - Admin",
        "This is a test email to admin. System is working! ✅"
    )
    results.append(f"Result: {'✅ ' if success else '❌ '} {msg}")
    
    results.append("<h2>Test 2: Customer Email</h2>")
    success, msg = send_resend_email(
        "josephedward201@gmail.com",
        "Final Test - Customer",
        "This is a test email to customer. System is working! ✅"
    )
    results.append(f"Result: {'✅ ' if success else '❌ '} {msg}")
    
    return HttpResponse("<br>".join(results))
