from rest_framework import serializers
from restaurant.models import RestaurantMenuSection, RestaurantTestimonial, RestaurantItemReview


class RestaurantMenuSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantMenuSection
        fields = ["id", "restaurant", "title", "cover_image", "description", "order", "layout_type"]
        extra_kwargs = {"restaurant": {"read_only": True}}


class RestaurantTestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantTestimonial
        fields = ["id", "restaurant", "name", "designation", "rating", "title", "text", "is_active"]
        extra_kwargs = {"restaurant": {"read_only": True}}


class RestaurantItemReviewSerializer(serializers.ModelSerializer):
    """Used for listing and updating reviews (admin moderation)."""
    member_name = serializers.SerializerMethodField()
    item_name = serializers.CharField(source="item.name", read_only=True)

    def get_member_name(self, obj):
        if obj.member:
            return obj.member.user.username
        return obj.reviewer_name or "Admin"

    class Meta:
        model = RestaurantItemReview
        fields = [
            "id", "item", "item_name",
            "member", "member_name", "reviewer_name", "reviewer_avatar",
            "rating", "review_text",
            "is_active", "created_at"
        ]
        extra_kwargs = {
            "member": {"read_only": True},
            "item": {"read_only": True},
            "created_at": {"read_only": True},
        }


class AdminReviewCreateSerializer(serializers.ModelSerializer):
    """Used only by admin to create a review manually (no member FK required)."""
    class Meta:
        model = RestaurantItemReview
        fields = ["reviewer_name", "reviewer_avatar", "rating", "review_text", "is_active"]
