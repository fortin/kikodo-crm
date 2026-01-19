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
router.register(r"dashboard-templates", views.DashboardTemplateViewSet)
router.register(r"custom-metrics", views.CustomMetricViewSet)
router.register(r"metric-data-points", views.MetricDataPointViewSet)
router.register(r"dashboard-views", views.DashboardViewViewSet)
# New Airtable-style endpoints
router.register(r"bases", views.BaseViewSet)
router.register(r"tables", views.TableViewSet)
router.register(r"table-fields", views.TableFieldViewSet)
router.register(r"records", views.RecordViewSet)

app_name = "analytics"

urlpatterns = [
    path("", views.analytics_dashboard, name="dashboard"),
    path("reports/", views.analytics_reports, name="reports"),
    path("templates/", views.analytics_templates, name="templates"),
    path("bases/", views.analytics_bases, name="bases"),
    path("api/", include(router.urls)),
]
