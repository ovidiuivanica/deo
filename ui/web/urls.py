from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^access$', views.access, name='access'),
    url(r'^data$', views.data, name='data'),
    url(r'^status$', views.status, name='status'),
    url(r'^stop$', views.stop, name='stop'),
    url(r'^start$', views.start, name='start'),
    url(r'^on$', views.on, name='on'),
    url(r'^off$', views.off, name='off'),
    url(r'^set/inc/(?P<room>\w{0,50})$', views.inc),
    url(r'^set/dec/(?P<room>\w{0,50})$', views.dec),
    url(r'^set_reference$', views.set_reference, name='set_reference'),
    url(r'^heat$', views.heat, name='heat'),
    url(r'^cold$', views.cold, name='cold'),
    url(r'^door$', views.door, name='door'),
    url(r'^alexandria$', views.alexandria),
    url(r'^tranzactii$', views.tranzactii),
    url(r'^achizitii$', views.achizitii),
    url(r'^test$', views.test),
    url(r'^link$', views.link),
    url(r'^copii$', views.copii),
    url(r'^advent$', views.advent),
    url(r'^lucrari$', views.lucrari),
    url(r'^cadouri$', views.cadouri),
    url(r'^familie$', views.familie),
    url(r'^aproape/(?P<familie>\w{0,50})$', views.aproape),
    url(r'^studiu$', views.studiu),
    url(r'^munte$', views.munte),
    url(r'^comanda/(?P<furnizor>\w{0,50})$', views.comanda)
]
