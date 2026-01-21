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

def get_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
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
    
    # Use stock_quantity__gt=0 instead of in_stock
    featured_products = Product.objects.filter(featured=True, stock_quantity__gt=0)[:4]
    
    context = {
        'brand_images': brand_images,
        'featured_products': featured_products,
        'search_form': SearchForm()
    }
    return render(request, 'home.html', context)

def products(request):
    category_slug = request.GET.get('category')
    products_list = Product.objects.all()  # Show all products
    
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
    # Remove the in_stock filter since we want to show the product even if out of stock
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
    
    # Check if product is in stock using stock_quantity
    if product.stock_quantity <= 0:
        messages.error(request, f"Sorry, {product.name} is out of stock.")
        return redirect('products')
    
    cart = get_cart(request)
    
    # Check if adding this item would exceed available stock
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
            
            # Send order confirmation email
            send_order_email_async(order, cart_items)
            
            # Clear the cart
            cart_items.delete()
            
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
    
    # Calculate time remaining
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
            
            # Send payment verification email
            send_payment_verification_email_async(order, customer_name)
            
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

def send_order_email_async(order, cart_items):
    """Send order email with proper threading and error handling."""
    def send_email():
        try:
            print("\n" + "="*60)
            print("STARTING EMAIL THREAD")
            print("="*60)
            
            items_text = "\n".join([f"- {item.product.name} (Qty: {item.quantity}) - ₦{item.total_price()}" 
                                   for item in cart_items])
            
            # Admin message
            admin_message = f"""
Order Details:
Order Number: {order.order_number}
Customer: {order.customer_name}
Email: {order.customer_email}
Phone: {order.customer_phone}
Address: {order.customer_address}, {order.city}, {order.state}

Items Ordered:
{items_text}

Total Amount: ₦{order.total_amount}

Payment Deadline: {order.payment_deadline.strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            print(f"\n📧 Attempting to send admin email for order {order.order_number}")
            print(f"To: {settings.RECIPIENT_EMAIL}")
            
            # Send to admin
            try:
                # Add timeout to prevent hanging
                import socket
                original_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(10)  # 10 second timeout
                
                from django.core.mail import send_mail
                
                num_sent = send_mail(
                    f'Order Confirmation - {order.order_number}',
                    admin_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.RECIPIENT_EMAIL],
                    fail_silently=False,
                )
                print(f"✅ Admin email sent. Result: {num_sent}")
                
                socket.setdefaulttimeout(original_timeout)
                
            except Exception as e:
                print(f"⚠️ Admin email warning: {type(e).__name__}: {e}")
                # Don't raise - just log and continue
            
            # Customer message
            customer_message = f"""
Thank you for your order {order.customer_name}!

Your order #{order.order_number} has been received.

Order Summary:
{items_text}

Total: ₦{order.total_amount}

Please make payment within 2 hours to secure your order.
"""
            
            print(f"\n📧 Attempting to send customer email for order {order.order_number}")
            print(f"To: {order.customer_email}")
            
            # Send to customer
            try:
                import socket
                socket.setdefaulttimeout(10)  # 10 second timeout
                
                num_sent = send_mail(
                    f'Order #{order.order_number} Confirmation',
                    customer_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [order.customer_email],
                    fail_silently=False,
                )
                print(f"✅ Customer email sent. Result: {num_sent}")
                
            except Exception as e:
                print(f"⚠️ Customer email warning: {type(e).__name__}: {e}")
            
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"\n🔥 Critical error in email thread: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Start thread with daemon=True so it doesn't block main process
    email_thread = threading.Thread(target=send_email, daemon=True)
    email_thread.start()
    
    # Also try to send sync version as fallback
    try:
        print("Starting fallback sync email attempt...")
        # Quick sync attempt with timeout
        import threading as th
        import queue
        
        result_queue = queue.Queue()
        
        def quick_send():
            try:
                from django.core.mail import send_mail
                num = send_mail(
                    'Order Received Sync',
                    f'Order {order.order_number} received. Check admin panel.',
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.RECIPIENT_EMAIL],
                    fail_silently=True,
                )
                result_queue.put(f"Sync result: {num}")
            except:
                result_queue.put("Sync failed")
        
        sync_thread = th.Thread(target=quick_send, daemon=True)
        sync_thread.start()
        sync_thread.join(timeout=5)  # Wait max 5 seconds
        
        if not result_queue.empty():
            print(result_queue.get())
        
    except:
        pass  # Ignore fallback errors
    
def send_payment_verification_email_async(order, customer_name):
    """Send payment verification email WITHOUT threading."""
    print(f"\n📧 Sending payment verification email for order {order.order_number}")
    
    message = f"""
Payment Verification Received:

Order Number: {order.order_number}
Customer: {customer_name}
Email: {order.customer_email}
Phone: {order.customer_phone}

Customer claims to have made payment. Please verify the transfer and update order status.

Order Details:
Amount: ₦{order.total_amount}
Items: {', '.join([item.product.name for item in order.orderitem_set.all()])}
"""
    
    try:
        from django.core.mail import send_mail
        
        num_sent = send_mail(
            f'Payment Verification - Order #{order.order_number}',
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.RECIPIENT_EMAIL],
            fail_silently=False,
        )
        print(f"✅ Payment verification email sent: {num_sent}")
        
    except Exception as e:
        print(f"❌ Payment verification email failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


# views.py
from django.core.mail import send_mail
from django.http import HttpResponse
import os

def test_resend_smtp(request):
    """Test Resend SMTP configuration"""
    results = []
    
    # Check config
    from django.conf import settings
    results.append("<h2>Current Email Configuration</h2>")
    results.append(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    results.append(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    results.append(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    results.append(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    results.append(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    
    api_key = os.environ.get('RESEND_API_KEY')
    results.append(f"RESEND_API_KEY: {'✅ SET' if api_key else '❌ NOT SET'}")
    if api_key:
        results.append(f"Key: {api_key[:10]}...")
    
    # Try to send email
    results.append("<h2>Test Email</h2>")
    try:
        num_sent = send_mail(
            'Test from Resend SMTP',
            f'This is a test email sent via Resend SMTP.\n\nTime: {timezone.now()}',
            settings.DEFAULT_FROM_EMAIL,
            ['markirving012@gmail.com'],  # Send to yourself
            fail_silently=False,  # Show errors
        )
        results.append(f"✅ Email sent successfully! Return value: {num_sent}")
        results.append("Check your email inbox (and spam folder)")
        
    except Exception as e:
        results.append(f"❌ Error: {type(e).__name__}")
        results.append(f"Details: {str(e)}")
        
        # Common errors and fixes
        if "authentication" in str(e).lower():
            results.append("<h3>Fix: Make sure your RESEND_API_KEY is correct</h3>")
        elif "connection refused" in str(e).lower():
            results.append("<h3>Fix: Railway might be blocking port 587. Try port 465 with SSL</h3>")
        elif "timeout" in str(e).lower():
            results.append("<h3>Fix: Increase EMAIL_TIMEOUT in settings</h3>")
    
    return HttpResponse("<br>".join(results))