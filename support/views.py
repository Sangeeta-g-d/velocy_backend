from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # optional, depending on your use-case
from admin_part.models import SupportCategory
from .serializers import SupportCategorySerializer



class SupportCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]  # optional, you can allow any user

    def get(self, request):
        categories = SupportCategory.objects.all().order_by('priority', 'name')
        serializer = SupportCategorySerializer(categories, many=True)
        return Response({
            "status": True,
            "message": "Support categories fetched successfully",
            "data": serializer.data
        })
