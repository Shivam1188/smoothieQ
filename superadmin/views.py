from django.shortcuts import render, HttpResponse

# Create your views here.

def superadmin(request):
    return HttpResponse('hello welcome to the superadmin api')