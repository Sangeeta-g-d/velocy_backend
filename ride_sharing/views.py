from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import RideShareVehicleSerializer
from .mixins import StandardResponseMixin

class AddRideShareVehicleAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RideShareVehicleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(owner=request.user)
            return self.response(serializer.data, 201)  # <-- ✅ Use self.response
        return self.response(serializer.errors, 400)   # <-- ✅ Use self.response
