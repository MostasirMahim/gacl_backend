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
        fields = ["id", "restaurant", "name", "designation", "rating", "title", "text"]
        extra_kwargs = {"restaurant": {"read_only": True}}


class RestaurantItemReviewSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.user.username", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = RestaurantItemReview
        fields = ["id", "item", "item_name", "member", "member_name", "rating", "review_text"]
        extra_kwargs = {
            "member": {"read_only": True},
            "item": {"read_only": True}
        }
