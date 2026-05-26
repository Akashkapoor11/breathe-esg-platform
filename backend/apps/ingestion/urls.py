from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IngestionJobViewSet, EmissionRecordViewSet, DashboardStatsView

router = DefaultRouter()
router.register(r'jobs', IngestionJobViewSet, basename='jobs')
router.register(r'records', EmissionRecordViewSet, basename='records')

urlpatterns = [
    path('', include(router.urls)),
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
]
