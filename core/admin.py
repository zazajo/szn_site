# szn_site/core/admin.py
from django.contrib import admin
from .models import Category, Product, Cart, CartItem, Order, OrderItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock_quantity', 'in_stock_display', 'featured']
    list_filter = ['category', 'featured']
    list_editable = ['price', 'stock_quantity', 'featured']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    
    def in_stock_display(self, obj):
        return obj.in_stock
    in_stock_display.boolean = True
    in_stock_display.short_description = 'In Stock'

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price', 'total_price']
    
    def total_price(self, obj):
        return f"₦{obj.total_price()}"
    total_price.short_description = 'Total'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer_name', 'customer_email', 'total_amount_display', 'status', 'payment_deadline', 'created_at']
    list_filter = ['status', 'created_at', 'city', 'state']
    search_fields = ['order_number', 'customer_name', 'customer_email', 'customer_phone']
    readonly_fields = ['order_number', 'total_amount', 'payment_deadline', 'created_at']
    inlines = [OrderItemInline]
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'status', 'total_amount', 'payment_deadline', 'created_at')
        }),
        ('Customer Information', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('Delivery Information', {
            'fields': ('customer_address', 'city', 'state')
        }),
    )
    
    def total_amount_display(self, obj):
        return f"₦{obj.total_amount}"
    total_amount_display.short_description = 'Total Amount'

admin.site.register(Cart)
admin.site.register(CartItem)