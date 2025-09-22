from django.urls import path
from .views import *

urlpatterns = [

    path('support-categories/', SupportCategoryListAPIView.as_view(), name='support-categories'),
    path('initiate-support-chat/', StartOrGetSupportChatAPIView.as_view(), name='initiate-support-chat'),
    path('send-support-message/', SendSupportMessageAPIView.as_view(), name='send-support-message'),
    path("support-chat-history/", UserSupportChatHistoryAPIView.as_view(), name="user_support_chat_history"),

]