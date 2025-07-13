from django.shortcuts import render, HttpResponse

# Create your views here.


def subadmin(request):
    return HttpResponse('Hello this is my subadmin profile')