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
    path("companies/", views.company_list, name="company_list"),
    path("deals/", views.deal_list, name="deal_list"),
    path("activities/", views.activity_list, name="activity_list"),
    path("api/", include(router.urls)),
]
