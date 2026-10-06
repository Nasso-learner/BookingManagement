from rest_framework.routers import DefaultRouter

from .views import DoctorViewSet, AvailabilityViewSet

router = DefaultRouter()
router.register("doctors", DoctorViewSet, basename="doctor")
router.register("availability", AvailabilityViewSet, basename="availability")
urlpatterns = router.urls
