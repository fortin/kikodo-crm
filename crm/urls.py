from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views, views

router = DefaultRouter()

router.register(r"companies", api_views.CompanyViewSet)
router.register(r"contacts", api_views.ContactViewSet)
router.register(r"deals", api_views.DealViewSet)
router.register(r"activities", api_views.ActivityViewSet)
router.register(r"tags", api_views.TagViewSet)
router.register(r"pipelines", api_views.PipelineViewSet)
router.register(r"pipeline-stages", api_views.PipelineStageViewSet)
router.register(r"contact-tags", api_views.ContactTagViewSet)
router.register(r"company-tags", api_views.CompanyTagViewSet)
router.register(r"deal-tags", api_views.DealTagViewSet)

app_name = "crm"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("contacts/", views.contact_list, name="contact_list"),
    path("contacts/delete/", views.contact_bulk_delete, name="contact_bulk_delete"),
    path("contacts/export/", views.contact_export_csv, name="contact_export_csv"),
    path("contacts/<int:pk>/", views.contact_detail, name="contact_detail"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact_edit"),
    path("contacts/add/", views.contact_create, name="contact_create"),
    path("contacts/import/", views.contact_import_csv, name="contact_import_csv"),
    path("contacts/duplicates/", views.contact_duplicates, name="contact_duplicates"),
    path("contacts/merge/", views.contact_merge, name="contact_merge"),
    path("companies/", views.company_list, name="company_list"),
    path("companies/delete/", views.company_bulk_delete, name="company_bulk_delete"),
    path("companies/export/", views.company_export_csv, name="company_export_csv"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("companies/<int:pk>/edit/", views.company_edit, name="company_edit"),
    path("companies/add/", views.company_create, name="company_create"),
    path("companies/import/", views.company_import_csv, name="company_import_csv"),
    path("companies/duplicates/", views.company_duplicates, name="company_duplicates"),
    path("companies/merge/", views.company_merge, name="company_merge"),
    path("import/", views.import_csv, name="import_csv"),
    path("deals/", views.deal_list, name="deal_list"),
    path("deals/kanban/", views.deal_kanban, name="deal_kanban"),
    path("deals/forecast/", views.deal_forecast, name="deal_forecast"),
    path("deals/move-stage/", views.deal_move_stage, name="deal_move_stage"),
    path("deals/add/", views.deal_create, name="deal_create"),
    path("deals/<int:pk>/", views.deal_detail, name="deal_detail"),
    path("deals/<int:pk>/edit/", views.deal_edit, name="deal_edit"),
    path("activities/", views.activity_list, name="activity_list"),
    path("activities/export/", views.activity_export_csv, name="activity_export_csv"),
    path("activities/<int:pk>/edit/", views.activity_edit, name="activity_edit"),
    path("activities/new/", views.activity_create, name="activity_create"),
    path(
        "activities/new/thread/<int:thread_id>/",
        views.activity_create,
        name="activity_create_from_thread",
    ),
    path("sequences/", views.sequence_list, name="sequence_list"),
    path("sequences/new/", views.sequence_create, name="sequence_create"),
    path("sequences/<int:pk>/", views.sequence_detail, name="sequence_detail"),
    path("sequences/<int:pk>/edit/", views.sequence_edit, name="sequence_edit"),
    path(
        "sequences/<int:pk>/enroll/",
        views.sequence_enroll,
        name="sequence_enroll",
    ),
    path(
        "contacts/<int:contact_pk>/enroll-sequence/",
        views.contact_enroll_sequence,
        name="contact_enroll_sequence",
    ),
    path("signals/", views.signal_list, name="signal_list"),
    path("signals/add/", views.signal_create, name="signal_create"),
    path("signals/export/", views.signal_export_csv, name="signal_export_csv"),
    path("signals/<int:pk>/", views.signal_detail, name="signal_detail"),
    path("signals/<int:pk>/edit/", views.signal_edit, name="signal_edit"),
    path("signals/<int:pk>/delete/", views.signal_delete, name="signal_delete"),
    path("unsubscribe/", views.unsubscribe, name="unsubscribe"),
    path("api/config/", api_views.config),
    path("api/token/", api_views.obtain_token),
    path("api/", include(router.urls)),
]
