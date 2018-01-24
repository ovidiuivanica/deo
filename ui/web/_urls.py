from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^status$', views.status, name='status'),
    url(r'^stop$', views.stop, name='stop'),
    url(r'^start', views.start, name='start'),
    url(r'^heat$', views.heat, name='heat'),
    url(r'^cold$', views.cold, name='cold'),
    url(r'^door$', views.door, name='door'),
    url(r'^light_start$', views.light_start, name='light_start'),
    url(r'^light_stop$', views.light_stop, name='light_stop'),
]
