from django.conf.urls.defaults import *

urlpatterns = patterns("infoserver.infobase.views",
    (r"^attendancelist/$", "section_list", {'template': "print/attendancelist.html"}),
    (r"^facesheet/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/$", "section_list", {'template': "print/facesheet.html"}),
    (r"^facesheetalpha/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/$", "section_list", {'template': "print/facesheetalpha.html"}),
    (r"^facestickers/$", "section_list", {'template': "print/facestickers.html"}),
    )