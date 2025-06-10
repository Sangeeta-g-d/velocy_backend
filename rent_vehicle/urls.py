from django.urls import path
from .views import *

rented_vehicle_edit_view = RentedVehicleEditViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
})


urlpatterns = [
    path('add-your-vehicle/', RentedVehicleCreateAPIView.as_view(), name='rented-vehicle-create'),
    path('my-garage/', UserRentedVehicleListAPIView.as_view(), name='user-rented-vehicle-list'),
    path('delete-rented-vehicle/<int:vehicle_id>/', DeleteRentedVehicleAPIView.as_view(), name='delete-rented-vehicle'),

    # user
    path('vehicles-details-edit/<int:pk>/', rented_vehicle_edit_view, name='rented-vehicle-detail'),
    path('car-rental-home-screen/', ApprovedVehiclesListAPIView.as_view(), name='approved-vehicles-list'),
    path('rental-vehicle-details/<int:vehicle_id>/', RentedVehicleDetailAPIView.as_view(), name='vehicle-detail'),
    path('lessor-documents/<int:vehicle_id>/', RentedVehicleOwnerInfoAPIView.as_view(), name='lessor-documents'),
    path('rent-request/<int:vehicle_id>/', CreateRentalRequestAPIView.as_view(), name='create-rental-request'),
    path('sent-rental-requests/', SentRentalRequestsAPIView.as_view(), name='sent-rental-requests'),

    # lessor
    path('lessor-rental-requests/', LessorRentalRequestsAPIView.as_view(), name='lessor-rental-requests'),
    path('rental-rider-profile/<int:rent_id>/', RentalRequestDetailAPIView.as_view(), name='rental-request-detail'),
    path('accept-rental-request/<int:rent_id>/', AcceptRentalRequestAPIView.as_view(), name='accept-rental-request'),
    path('reject-rental-request/<int:rent_id>/', RejectRentalRequestAPIView.as_view(), name='accept-rental-request'),
    path('car-handover-detials/<int:rent_request_id>/', RentalRequestVehicleInfoAPIView.as_view(), name='rental-vehicle-info'),
    path('vehicle-handover/<int:rental_request_id>/', HandoverChecklistAPIView.as_view(), name='handover-checklist'),
    path('approved-rental-request/<int:rental_request_id>/', RentalHandoverDetailAPIView.as_view(), name='rental-handover-details'),
    path('handover-details/<int:rental_request_id>/', RentalHandoverDetailAPIView.as_view(), name='rental-handover-details'),
    
]  