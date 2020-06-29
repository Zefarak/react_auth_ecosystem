from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ProductListView, ProductCreateApiView, homepage, VendorViewSet, BrandViewSet


app_name = 'products'

router = DefaultRouter()
router.register('brands', BrandViewSet, basename='brand')
router.register('vendors', VendorViewSet, basename='vendor')

urlpatterns = [
    path('home/', homepage, name='home'),
    path('list/', ProductListView.as_view(), name='list'),
    path('create/', ProductCreateApiView.as_view(), name='create'),

   
] + router.urls
