
from rest_framework import serializers
from .models import Venue
from .models import COUNTRY_CHOICES,Event,EventTicket,EventFee,EventMedia,EVENT_STATUS_CHOICES,EVENT_TICKET_STATUS_CHOICES
from core.models import MembershipType
from member.models import Member
from promo_code_app.models import PromoCode
import pdb

class EventVenueSerializer(serializers.Serializer):
    street_address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=255)
    state_province = serializers.CharField(max_length=255, required=False, default="")
    postal_code = serializers.CharField(max_length=20, required=False, default="")
    country = serializers.ChoiceField(choices=COUNTRY_CHOICES)

    def validate_street_address(self, value):
        """
        Ensure street address is not too short.
        """
        if len(value) < 5:
            raise serializers.ValidationError("Street address must be at least 5 characters")
        return value

    def validate_city(self, value):
        """
        Ensure city is not too short.
        """
        if len(value) < 3:
            raise serializers.ValidationError("City name is too short.")
        return value

    def validate_postal_code(self, value):
        """
        Ensure postal code is valid if provided.
        """
        if value and len(value) < 5:
            raise serializers.ValidationError("Postal code must be at least 4 characters.")
        return value

    def validate(self, data):
        """
        Cross-field validation (e.g., postal code validation).
        """
        # Example: Check if postal code and state are required together.
        if data.get("state_province") and not data.get("postal_code"):
            raise serializers.ValidationError({"postal_code": ["Postal code is required when state/province is provided."]})
    
        return data
    
    def create(self, validated_data):
        """
        Create a new Venue instance.
        """
        venue = Venue.objects.create(**validated_data)
        return venue
        
class EventVenueViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = "__all__"

class EventTicketSerializer(serializers.Serializer):
    ticket_name = serializers.CharField(max_length=255)
    ticket_description = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    capacity = serializers.IntegerField(min_value=1)
    start_sale_date = serializers.DateTimeField()
    end_sale_date = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=EVENT_TICKET_STATUS_CHOICES, default='available')
    event = serializers.IntegerField() 

    def validate_ticket_name(self, value):
        if EventTicket.objects.filter(ticket_name=value).exists():
            raise serializers.ValidationError("An event ticket with this name already exists.")
        return value

    def validate_event(self, value):
        try:
            event_instance = Event.objects.get(pk=value)
        except Event.DoesNotExist:
            raise serializers.ValidationError("Event does not exist.")
        return event_instance

    def create(self, validated_data):
        ticket = EventTicket.objects.create(**validated_data)
        return ticket

class EventMediaSerializer(serializers.Serializer):
    image = serializers.FileField()
    event = serializers.IntegerField()

    def validate_event(self, value):
        try:
            event_instance = Event.objects.get(pk=value)
        except Event.DoesNotExist:
            raise serializers.ValidationError("Event does not exist.")
        return event_instance

    def create(self, validated_data):
        media = EventMedia.objects.create(**validated_data)
        return media

class EventMediaViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventMedia
        fields = "__all__"
   
class EventFeeSerializer(serializers.Serializer):
    fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    event = serializers.IntegerField()
    membership_type = serializers.CharField()
    
    def validate_event(self, value):
        try:
            event_instance = Event.objects.get(pk=value)
        except Event.DoesNotExist:
            raise serializers.ValidationError("Event does not exist.")
        return event_instance

    def validate_membership_type(self, value):
        try:
            membership_type_instance = MembershipType.objects.get(name=value)
        except MembershipType.DoesNotExist:
            raise serializers.ValidationError("Membership type does not exist.")
        return membership_type_instance

    def validate(self, attrs):
        event = attrs.get('event')
        membership_type = attrs.get('membership_type')
        if EventFee.objects.filter(event=event, membership_type=membership_type).exists():
            raise serializers.ValidationError("Fee for this event and membership type already exists.")
        return attrs
    
    def create(self, validated_data):
        fee = EventFee.objects.create(**validated_data)
        return fee

class EventFeeViewSerializer(serializers.ModelSerializer):
    membership_type = serializers.SerializerMethodField()
    class Meta:
        model = EventFee
        fields = "__all__"
        
    def get_membership_type(self, obj):
        return {
            "name": obj.membership_type.name,
            "id": obj.membership_type.id
        } if obj.membership_type else None

class EventSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=EVENT_STATUS_CHOICES)
    registration_deadline = serializers.DateTimeField()
    event_type = serializers.CharField(max_length=255)
    reminder_time = serializers.DateTimeField()
    venue = serializers.IntegerField(required=False, allow_null=True)
    organizer = serializers.CharField(required=False, allow_null=True)

    def validate_title(self, value):
        
        if Event.objects.filter(title=value).exists():
            raise serializers.ValidationError("An event with this title already exists.")
        return value
    
    def validate_venue(self, value):
        try:
            venue_instance = Venue.objects.get(pk=value)
        except Venue.DoesNotExist:
            raise serializers.ValidationError("Venue does not exist.")
        return venue_instance 
    
    def validate_organizer(self, value):
        try:
            organizer_instance = Member.objects.get(member_ID=value)
        except Member.DoesNotExist:
            raise serializers.ValidationError(f"Organizer {value} does not exist.")
        return organizer_instance    

    def create(self, validated_data):
        """
        Create a new Event instance.
        """
        event = Event.objects.create(**validated_data)
        return event

class EventOrganizerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['member_ID','first_name','last_name','membership_type']  # Only return the needed field


class EventViewSerializer(serializers.ModelSerializer):
    venue = EventVenueViewSerializer(read_only=True)
    organizer = EventOrganizerSerializer(read_only=True)
    media = EventMediaViewSerializer(many=True, source='event_media', read_only=True)

    class Meta:
        model = Event
        fields = "__all__"

class EventTicketViewSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = EventTicket
        fields = "__all__"


class EventTicketBuySerializer(serializers.Serializer):
    event_ticket = serializers.PrimaryKeyRelatedField(queryset=EventTicket.objects.filter(status='available'))
    member_ID = serializers.CharField()
    promo_code = serializers.CharField(required=False, default=None)

    
    def validate_member_ID(self, value):
        if not Member.objects.filter(member_ID=value).exists():
            raise serializers.ValidationError(f"{value} is not a member")
        return value
    def validate_promo_code(self, value):
        if not value:
            return value

        try:
            promo_code = PromoCode.objects.get(promo_code=value)
        except PromoCode.DoesNotExist:
            raise serializers.ValidationError("This is not a valid promo code.")

        if not promo_code.is_promo_code_valid():
            raise serializers.ValidationError("This promo code is expired or not valid any more.")

        if not promo_code.category.filter(name__iexact="event").exists():
            raise serializers.ValidationError("This is not an event category promo code.")

        return promo_code

            

# ===== EVENT EXPENSE / FOOD TRACKING SERIALIZERS =====
from event.models import EventExpenseCategory, EventExpense, EventFoodItem


class EventExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventExpenseCategory
        fields = ["id", "name", "is_active"]


class EventExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventExpense
        fields = ["id", "event", "category", "kind", "title", "description",
                  "quantity", "unit_cost", "amount", "is_active"]
        extra_kwargs = {"amount": {"required": False}}


class EventFoodItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventFoodItem
        fields = ["id", "event", "name", "quantity", "unit", "estimated_cost",
                  "expense", "is_active"]
