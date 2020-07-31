from django.conf.urls.defaults import *

urlpatterns = patterns("equipment.views",
    (r"^checkout/(?:(?P<due_timestamp>\d{4}-\d{1,2}-\d{1,2}-\d{1,2}-\d{2})/)?(?:(?P<person_id>\d+)/)?", "check_out"),
    (r"^checkin/$", "check_in"),
    (r"^item/", "item"),
    (r"^person/", "person"),
    (r"^report/(?:(?P<report_kind>[\w-]+)/(?:(?P<number>\w+)/)?)?$", "report"),
    (r"^find/$", "find"),
    (r"^add/$", "add"),
    (r"^buildkit/(?:(?P<kit_id>.+)/)?$", "buildkit"),
    (r"^statement/(?:(?P<person_id>\d+)/)?$", "penalty_statement"),
    (r"^$", "home"),
    )