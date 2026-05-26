from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers


class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'full_name': self.user.get_full_name(),
            'role': self.user.role,
            'organization': {
                'id': str(self.user.organization.id),
                'name': self.user.organization.name,
                'slug': self.user.organization.slug,
            } if self.user.organization else None,
        }
        return data


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer
