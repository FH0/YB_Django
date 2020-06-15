from django.shortcuts import render
from django.views.decorators import csrf
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


# 显示主页
def index(request):
    return render(request, 'yb.html', {})
