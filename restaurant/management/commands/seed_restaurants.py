import datetime
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from restaurant.models import (
    Restaurant,
    RestaurantCategory,
    RestaurantCuisineCategory,
    RestaurantItemCategory,
    RestaurantMenuSection,
    RestaurantItem,
    RestaurantTestimonial,
    RestaurantItemReview
)

class Command(BaseCommand):
    help = 'Seeds database with default premium restaurants, menu sections, items, and reviews.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting restaurant database seeding..."))

        # 1. Create categories
        cuisine_type, _ = RestaurantCuisineCategory.objects.get_or_create(name="Multicuisine")
        restaurant_type, _ = RestaurantCategory.objects.get_or_create(name="Fine Dining")

        # 2. Cleanup old seed restaurant if it exists to allow re-running
        slug = "burger-house"
        for old_restaurant in Restaurant.objects.filter(slug=slug):
            # Delete reviews for this restaurant's items
            RestaurantItemReview.objects.filter(item__restaurant=old_restaurant).delete()
            # Delete items
            RestaurantItem.objects.filter(restaurant=old_restaurant).delete()
            # Delete testimonials
            RestaurantTestimonial.objects.filter(restaurant=old_restaurant).delete()
            # Delete sections
            RestaurantMenuSection.objects.filter(restaurant=old_restaurant).delete()
            # Finally delete the restaurant
            old_restaurant.delete()
        
        # 3. Create a default premium Restaurant
        restaurant = Restaurant.objects.create(
            name="Burger House",
            slug=slug,
            description="Experience gourmet burgers, hand-crafted sides, and signature desserts prepared by world-class chefs in a cozy, modern atmosphere.",
            address="123 Club House Way, Suite A",
            city="Metropolis",
            state="NY",
            postal_code="10001",
            phone="+1234567890",
            operating_hours=12,
            capacity=100,
            status="open",
            opening_time=datetime.time(10, 0),
            closing_time=datetime.time(22, 0),
            booking_fees_per_seat=5.00,
            cuisine_type=cuisine_type,
            restaurant_type=restaurant_type,
            banner_title="Burger House Gourmet Club",
            banner_description="Savor our collection of prime-aged beef burgers, freshly baked brioche buns, and artisan ingredients crafted to perfection.",
            about_text="Founded in 2018, Burger House brings a refined twist to casual classic dining. We source our beef from certified local organic farms, and our secret burger sauce is prepared fresh daily. Enjoy an upscale club atmosphere combined with comfort food at its absolute finest.",
            meta_title="Burger House - Premium Club Diner",
            meta_description="Indulge in high-quality gourmet burgers, freshly cut fries, and premium craft shakes at the Burger House Club.",
            delivery_banner_title="30 Minutes Club Delivery!",
            delivery_banner_text="We guarantee your order arrives hot and fresh within 30 minutes, or it is completely on us.",
            reservation_banner_title="Reserve Your Favorite Cozy Corner",
            reservation_banner_text="Plan your private dining experience, birthday, or corporate lunch with our flexible seating options.",
            reservation_banner_launch_menu="15+ items",
            reservation_banner_dinner_menu="25+ items",
            footer_config={
                "tagline": "Crafting premium culinary memories since 2018.",
                "socials": {
                    "facebook": "https://facebook.com/burgerhouse",
                    "instagram": "https://instagram.com/burgerhouse",
                    "twitter": "https://twitter.com/burgerhouse"
                }
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Created Restaurant: {restaurant.name}"))

        # 4. Create Menu Sections
        sections_data = [
            {"title": "Gourmet Burgers", "order": 1, "description": "Our signature premium burgers made from 100% organic Black Angus beef."},
            {"title": "Sides & Appetizers", "order": 2, "description": "Perfect starters and companions to complete your meal."},
            {"title": "Artisan Desserts", "order": 3, "description": "Sweet indulgences crafted fresh in our kitchen daily."},
            {"title": "Drinks & Shakes", "order": 4, "description": "Crafted sodas, thick premium milkshakes, and fresh juices."}
        ]

        sections = {}
        for sec in sections_data:
            section = RestaurantMenuSection.objects.create(
                restaurant=restaurant,
                title=sec["title"],
                description=sec["description"],
                order=sec["order"],
                layout_type="default"
            )
            sections[sec["title"]] = section
            self.stdout.write(self.style.SUCCESS(f"  Created Menu Section: {section.title}"))

        # 5. Create Item Categories
        item_categories = {}
        for cat_name in ["Burgers", "Appetizers", "Desserts", "Beverages"]:
            cat, _ = RestaurantItemCategory.objects.get_or_create(name=cat_name)
            item_categories[cat_name] = cat

        # 6. Create Menu Items
        items_data = [
            # Gourmet Burgers
            {
                "name": "The Classic Cheese Burger",
                "description": "Premium Black Angus beef patty, melted cheddar cheese, leaf lettuce, vine-ripened tomato, and our signature Burger House sauce on a toasted brioche bun.",
                "unit": "pcs",
                "unit_cost": 5.00,
                "selling_price": 12.00,
                "half_price": 7.00,
                "category": item_categories["Burgers"],
                "menu_section": sections["Gourmet Burgers"],
                "stock": 50,
                "free_bonus": "Free french fries with every order",
                "sub_items": "Double Cheese, Crispy Bacon, Caramelized Onions",
                "tags": ["Cheese", "Pizza", "Best Seller"],
                "sku": "BH-CLASSIC-01"
            },
            {
                "name": "Bacon Avocado Burger",
                "description": "Flame-grilled organic beef, crispy hickory-smoked bacon, fresh avocado slices, Swiss cheese, and garlic aioli.",
                "unit": "pcs",
                "unit_cost": 6.50,
                "selling_price": 15.00,
                "half_price": 9.00,
                "category": item_categories["Burgers"],
                "menu_section": sections["Gourmet Burgers"],
                "stock": 40,
                "free_bonus": "Complimentary soft drink",
                "sub_items": "Jalapenos, Fried Egg, Extra Patty",
                "tags": ["Avocado", "Bacon", "Spicy"],
                "sku": "BH-AVO-BACON-02"
            },
            {
                "name": "Smoked BBQ Beast Burger",
                "description": "Double beef patty, smoked provolone cheese, onion rings, pickled jalapenos, and sweet BBQ glaze.",
                "unit": "pcs",
                "unit_cost": 8.00,
                "selling_price": 18.00,
                "half_price": 10.50,
                "category": item_categories["Burgers"],
                "menu_section": sections["Gourmet Burgers"],
                "stock": 30,
                "free_bonus": "Free onion rings upgrade",
                "sub_items": "Pulled Pork topping, Cheddar sauce",
                "tags": ["BBQ", "Spicy", "Chef Special"],
                "sku": "BH-BBQ-BEAST-03"
            },

            # Sides & Appetizers
            {
                "name": "Truffle Parmesan Fries",
                "description": "Hand-cut Idaho potatoes tossed in white truffle oil, grated parmesan cheese, and fresh parsley, served with house garlic aioli.",
                "unit": "plate",
                "unit_cost": 2.00,
                "selling_price": 6.00,
                "half_price": 4.00,
                "category": item_categories["Appetizers"],
                "menu_section": sections["Sides & Appetizers"],
                "stock": 100,
                "tags": ["Vegetarian", "Cheesy"],
                "sku": "BH-TRUFFLE-FRIES"
            },
            {
                "name": "Crispy Buffalo Wings",
                "description": "Juicy chicken wings tossed in our signature tangy buffalo hot sauce, served with celery sticks and blue cheese dressing.",
                "unit": "6 pcs",
                "unit_cost": 3.50,
                "selling_price": 9.50,
                "half_price": 5.50,
                "category": item_categories["Appetizers"],
                "menu_section": sections["Sides & Appetizers"],
                "stock": 60,
                "tags": ["Chicken", "Spicy"],
                "sku": "BH-BUFFALO-WINGS"
            },

            # Artisan Desserts
            {
                "name": "Molten Chocolate Lava Cake",
                "description": "Rich chocolate cake with a warm, liquid chocolate center, served with a scoop of premium vanilla bean gelato.",
                "unit": "pcs",
                "unit_cost": 2.50,
                "selling_price": 8.00,
                "category": item_categories["Desserts"],
                "menu_section": sections["Artisan Desserts"],
                "stock": 25,
                "tags": ["Sweet", "Chocolate"],
                "sku": "BH-LAVA-CAKE"
            },
            {
                "name": "Classic New York Cheesecake",
                "description": "Velvety smooth cream cheese filling on a graham cracker crust, topped with fresh strawberry compote.",
                "unit": "slice",
                "unit_cost": 2.00,
                "selling_price": 7.50,
                "category": item_categories["Desserts"],
                "menu_section": sections["Artisan Desserts"],
                "stock": 35,
                "tags": ["Sweet", "Berry"],
                "sku": "BH-CHEESECAKE"
            },

            # Drinks & Shakes
            {
                "name": "Premium Salted Caramel Shake",
                "description": "Creamy vanilla milkshake blended with house-made sea-salted caramel sauce, topped with whipped cream and pretzels.",
                "unit": "glass",
                "unit_cost": 1.50,
                "selling_price": 6.50,
                "category": item_categories["Beverages"],
                "menu_section": sections["Drinks & Shakes"],
                "stock": 80,
                "tags": ["Cold", "Caramel"],
                "sku": "BH-CARAMEL-SHAKE"
            },
            {
                "name": "Fresh Mint Limeade",
                "description": "Refreshing cold-pressed lime juice, crushed fresh garden mint, pure organic cane sugar, and sparkling water.",
                "unit": "glass",
                "unit_cost": 0.80,
                "selling_price": 4.50,
                "category": item_categories["Beverages"],
                "menu_section": sections["Drinks & Shakes"],
                "stock": 120,
                "tags": ["Cold", "Refreshing"],
                "sku": "BH-MINT-LIMEADE"
            }
        ]

        created_items = []
        for item_info in items_data:
            item = RestaurantItem.objects.create(
                restaurant=restaurant,
                name=item_info["name"],
                slug=slugify(item_info["name"]),
                description=item_info["description"],
                unit=item_info["unit"],
                unit_cost=item_info["unit_cost"],
                selling_price=item_info["selling_price"],
                half_price=item_info.get("half_price"),
                category=item_info["category"],
                menu_section=item_info["menu_section"],
                stock=item_info["stock"],
                free_bonus=item_info.get("free_bonus", ""),
                sub_items=item_info.get("sub_items", ""),
                tags=item_info.get("tags", []),
                sku=item_info["sku"]
            )
            created_items.append(item)
            self.stdout.write(self.style.SUCCESS(f"    Created Menu Item: {item.name}"))

        # 7. Create Restaurant Testimonials
        testimonials_data = [
            {
                "name": "Matthew J. Wyman",
                "designation": "Senior Consultant",
                "rating": 5,
                "title": "The best burger ever!",
                "text": "The Classic Cheese Burger is absolutely spectacular. The brioche bun was incredibly soft and the patty was juicy and seasoned perfectly. Clean, premium environment and friendly staff."
            },
            {
                "name": "Istiak Ahmed",
                "designation": "Marketing Manager",
                "rating": 5,
                "title": "Awesome and delicious food",
                "text": "Highly recommend the Truffle Parmesan Fries and the Salted Caramel Shake! Burger House has completely redefined upscale comfort dining for me. Will be ordering regularly."
            }
        ]

        for test in testimonials_data:
            testimonial = RestaurantTestimonial.objects.create(
                restaurant=restaurant,
                name=test["name"],
                designation=test["designation"],
                rating=test["rating"],
                title=test["title"],
                text=test["text"]
            )
            self.stdout.write(self.style.SUCCESS(f"  Created Testimonial from: {testimonial.name}"))

        # 8. Create Item Reviews
        item_reviews_data = {
            "The Classic Cheese Burger": [
                {
                    "reviewer_name": "Sarah Jenkins",
                    "rating": 5,
                    "review_text": "An absolute masterpiece. Searing is perfect and the burger sauce makes it taste completely unique. Must try!"
                },
                {
                    "reviewer_name": "David Miller",
                    "rating": 4,
                    "review_text": "Very delicious and satisfying. Fries were crisp. The burger bun was slightly toasted too much, but still extremely good."
                }
            ],
            "Truffle Parmesan Fries": [
                {
                    "reviewer_name": "Emily Watson",
                    "rating": 5,
                    "review_text": "The aroma of truffle is wonderful and the portion size is very generous. Best fries in the city!"
                }
            ]
        }

        for item in created_items:
            reviews = item_reviews_data.get(item.name, [
                {
                    "reviewer_name": "John Doe",
                    "rating": 5,
                    "review_text": f"Excellent quality and fantastic taste. The {item.name} is a stellar choice."
                }
            ])
            for rev in reviews:
                review = RestaurantItemReview.objects.create(
                    item=item,
                    reviewer_name=rev["reviewer_name"],
                    rating=rev["rating"],
                    review_text=rev["review_text"]
                )
                self.stdout.write(self.style.SUCCESS(f"    Created Review for {item.name} by {review.reviewer_name}"))

        self.stdout.write(self.style.SUCCESS("Restaurant database seeding completed successfully!"))
