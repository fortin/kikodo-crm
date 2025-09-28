from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"dashboard-widgets", views.DashboardWidgetViewSet)
router.register(r"reports", views.ReportViewSet)
router.register(r"sales-goals", views.SalesGoalViewSet)
router.register(r"activity-summaries", views.ActivitySummaryViewSet)
router.register(r"pipeline-snapshots", views.PipelineSnapshotViewSet)
router.register(r"contact-engagement", views.ContactEngagementViewSet)
router.register(r"deal-forecasts", views.DealForecastViewSet)
router.register(r"custom-fields", views.CustomFieldViewSet)
router.register(r"custom-field-values", views.CustomFieldValueViewSet)

app_name = "analytics"

urlpatterns = [
    path("", views.analytics_dashboard, name="dashboard"),
    path("reports/", views.analytics_reports, name="reports"),
    path("api/", include(router.urls)),
]
