from django.conf.urls.defaults import *
from django.conf import settings
from infoserver.infobase.models import Person


# Attendance system
urlpatterns = patterns("infoserver.infobase.views",
    (r"^scan/", "scan"),
    (r"^attendance/$", "attendance"),
    (r"^attendance/(?P<class_id>\d+)/$", "attendance"),
    (r"^attendance/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/$", "attendance"),
    (r"^report/$", "report"),
    (r"^report/student/(?P<student_id>\d+)?/?$", "student_report"),
    (r"^report/noshow/$", "noshow"),
    (r"^report/(?P<class_id>\d+)/$", "report"),
    (r"^report/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/$", "report"),
    (r"^report/whereis/(?P<person_id>\d{7})/$", "report"),
    (r"^status/$", "status"),
    (r"^faces/(?P<section>\w+)?/?$", "faces"),
    (r"^schedule/$", "schedule"),
    (r"^flagged/(?:(?P<flag_name>.+)/)?$", "flagged_people"),
    (r"^api/students/", "students_api"),
    (r"^admin/infobase/phonelist/$", "phone_list"),
    (r"^admin/scheduler/(?:(?P<datestring>.+)/)?$", "schedule_builder"),
    )

# Equipment system
urlpatterns += patterns("", 
    (r"^equipment/", include("infoserver.equipment.urls")))

# Contrib apps
urlpatterns += patterns("",
    (r"^admin/", include("django.contrib.admin.urls")),
    (r"^accounts/$", "django.contrib.auth.views.login"),
    (r"^accounts/login/$", "django.contrib.auth.views.login"),
    (r"^accounts/logout/$", "django.contrib.auth.views.logout"),
    )

# Static serving for dev server only; Apache doesn't pass Django /static/* URLs
urlpatterns += patterns("",
    (r"^static/(?P<path>.*)$", "django.views.static.serve", {'document_root': settings.MEDIA_ROOT}),
    )