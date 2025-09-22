from django.urls import path
from .views import *

urlpatterns = [

    path('support-categories/', SupportCategoryListAPIView.as_view(), name='support-categories'),

]