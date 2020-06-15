from django.conf.urls import url
from . import index,yb

urlpatterns = [
    url(r'^$', index.index),
    url(r'^login$', yb.login),
    url(r'^captcha$', yb.captcha),
]
