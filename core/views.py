from django.shortcuts import render

# Create your views here.

def home(request):
    """Vista principal del dashboard"""
    return render(request, 'base.html')