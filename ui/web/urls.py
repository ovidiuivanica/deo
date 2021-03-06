from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^status$', views.status, name='status'),
    url(r'^data$', views.data, name='data'),
    url(r'^stop$', views.stop, name='stop'),
    url(r'^start$', views.start, name='start'),
    url(r'^on$', views.on, name='on'),
    url(r'^off$', views.off, name='off'),
    url(r'^set_reference$', views.set_reference, name='set_reference'),
    url(r'^heat$', views.heat, name='heat'),
    url(r'^cold$', views.cold, name='cold'),
    url(r'^door$', views.door, name='door'),
    url(r'^light_start$', views.light_start, name='light_start'),
    url(r'^light_stop$', views.light_stop, name='light_stop'),
]

