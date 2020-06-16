from django.conf.urls import url
from . import index,yb

urlpatterns = [
    url(r'^$', index.index),
    url(r'^login$', yb.login),
    url(r'^is_login$', yb.is_login),
    url(r'^rush_yb$', yb.rush_yb),
    url(r'^captcha$', yb.captcha),
    url(r'^wangxin_jingyan$', yb.wangxin_jingyan),
]
