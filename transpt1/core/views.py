from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from core.models import Company
from core.permissions import IsSameCompany
from core.serializers import CompanySerializer, UserSerializer


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CompanyDetailView(RetrieveAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, IsSameCompany]
