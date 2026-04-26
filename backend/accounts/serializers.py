"""Serializers for signup, login, and the /me endpoint."""

from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

User = get_user_model()


# Returned wherever we expose a user.
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role"]
        read_only_fields = fields


# Used by POST /auth/signup/. Defaults role to merchant.
class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["email", "password", "role"]
        extra_kwargs = {"role": {"required": False}}

    def validate_role(self, value):
        if value not in (User.ROLE_MERCHANT, User.ROLE_REVIEWER):
            raise serializers.ValidationError("role must be 'merchant' or 'reviewer'.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        email = validated_data["email"].lower()
        user = User(
            email=email,
            username=email,
            role=validated_data.get("role", User.ROLE_MERCHANT),
        )
        user.set_password(password)
        user.save()
        return user


# Used by POST /auth/login/. Returns the user if credentials match.
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        # authenticate() honours password hashing + active flag.
        user = authenticate(username=email, password=attrs["password"])
        if user is None:
            # Fallback in case the user was created with a different username.
            try:
                candidate = User.objects.get(email=email)
            except User.DoesNotExist:
                candidate = None
            if candidate and candidate.check_password(attrs["password"]):
                user = candidate
        if user is None:
            raise serializers.ValidationError({"detail": "Invalid email or password."})
        attrs["user"] = user
        return attrs
