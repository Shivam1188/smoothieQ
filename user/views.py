from django.shortcuts import render, HttpResponse

# Create your views here.


def user(request):
    return HttpResponse("hello welcome to my user api's")