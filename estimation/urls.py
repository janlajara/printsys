from django.urls import path
from . import views

urlpatterns = [
    path('fit_sheets/', views.FitSheetAPIView.as_view(), name='fit_sheets')
]