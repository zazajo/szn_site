from .models import Cart, CartItem

def cart_items_count(request):
    count = 0
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            count = CartItem.objects.filter(cart=cart).count()
        except Cart.DoesNotExist:
            pass
    else:
        session_key = request.session.session_key
        if session_key:
            try:
                cart = Cart.objects.get(session_key=session_key)
                count = CartItem.objects.filter(cart=cart).count()
            except Cart.DoesNotExist:
                pass
    return {'cart_items_count': count}