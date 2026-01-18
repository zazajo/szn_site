from django import forms
from .models import Product
from .models import Order

class SearchForm(forms.Form):
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search products...',
            'class': 'search-input'
        })
    )


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer_name', 'customer_email', 'customer_phone', 'customer_address', 'city', 'state']
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'placeholder': 'Name (must match bank account name)',
                'class': 'form-input'
            }),
            'customer_email': forms.EmailInput(attrs={
                'placeholder': 'Email address',
                'class': 'form-input'
            }),
            'customer_phone': forms.TextInput(attrs={
                'placeholder': 'Phone number',
                'class': 'form-input'
            }),
            'customer_address': forms.Textarea(attrs={
                'placeholder': 'Delivery address',
                'class': 'form-input',
                'rows': 3
            }),
            'city': forms.TextInput(attrs={
                'placeholder': 'City',
                'class': 'form-input'
            }),
            'state': forms.TextInput(attrs={
                'placeholder': 'State',
                'class': 'form-input'
            }),
        }
    
    def clean_customer_name(self):
        name = self.cleaned_data['customer_name']
        if len(name.strip()) < 2:
            raise forms.ValidationError("Please enter a valid name.")
        return name.strip()

class PaymentVerificationForm(forms.Form):
    customer_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your name as confirmation',
            'class': 'form-input'
        })
    )
    
    def clean_customer_name(self):
        name = self.cleaned_data['customer_name']
        if len(name.strip()) < 2:
            raise forms.ValidationError("Please enter your name.")
        return name.strip()