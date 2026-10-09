from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "role"]


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    access_expires_in = serializers.IntegerField(help_text="Seconds until the access token expires")
    user = UserSerializer()
