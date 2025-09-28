import random
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.models import Activity, Company, Contact, Deal, Tag


class Command(BaseCommand):
    help = "Populate the database with sample CRM data"

    def handle(self, *args, **options):
        self.stdout.write("Creating sample data...")

        # Create a test user if it doesn't exist
        user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "first_name": "Admin",
                "last_name": "User",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password("admin123")
            user.save()

        # Create sample companies
        companies_data = [
            {
                "name": "Acme Corporation",
                "industry": "Technology",
                "phone": "+1-555-0101",
                "email": "info@acme.com",
            },
            {
                "name": "Global Solutions Inc",
                "industry": "Consulting",
                "phone": "+1-555-0102",
                "email": "contact@globalsolutions.com",
            },
            {
                "name": "TechStart LLC",
                "industry": "Software",
                "phone": "+1-555-0103",
                "email": "hello@techstart.com",
            },
            {
                "name": "DataFlow Systems",
                "industry": "Data Analytics",
                "phone": "+1-555-0104",
                "email": "info@dataflow.com",
            },
            {
                "name": "CloudTech Partners",
                "industry": "Cloud Services",
                "phone": "+1-555-0105",
                "email": "partners@cloudtech.com",
            },
        ]

        companies = []
        for company_data in companies_data:
            company, created = Company.objects.get_or_create(
                name=company_data["name"],
                defaults={
                    **company_data,
                    "owner": user,
                    "annual_revenue": random.randint(1000000, 50000000),
                    "employee_count": random.randint(10, 500),
                    "city": "San Francisco",
                    "state": "CA",
                    "country": "USA",
                },
            )
            companies.append(company)

        # Create sample contacts
        contacts_data = [
            {
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@acme.com",
                "job_title": "CEO",
            },
            {
                "first_name": "Sarah",
                "last_name": "Johnson",
                "email": "sarah.johnson@globalsolutions.com",
                "job_title": "VP Sales",
            },
            {
                "first_name": "Mike",
                "last_name": "Davis",
                "email": "mike.davis@techstart.com",
                "job_title": "CTO",
            },
            {
                "first_name": "Emily",
                "last_name": "Wilson",
                "email": "emily.wilson@dataflow.com",
                "job_title": "Marketing Director",
            },
            {
                "first_name": "David",
                "last_name": "Brown",
                "email": "david.brown@cloudtech.com",
                "job_title": "Sales Manager",
            },
            {
                "first_name": "Lisa",
                "last_name": "Garcia",
                "email": "lisa.garcia@acme.com",
                "job_title": "Product Manager",
            },
            {
                "first_name": "Tom",
                "last_name": "Martinez",
                "email": "tom.martinez@globalsolutions.com",
                "job_title": "Account Executive",
            },
            {
                "first_name": "Anna",
                "last_name": "Anderson",
                "email": "anna.anderson@techstart.com",
                "job_title": "Business Analyst",
            },
        ]

        contacts = []
        for i, contact_data in enumerate(contacts_data):
            contact, created = Contact.objects.get_or_create(
                email=contact_data["email"],
                defaults={
                    **contact_data,
                    "company": companies[i % len(companies)],
                    "owner": user,
                    "phone": f"+1-555-{random.randint(1000, 9999)}",
                    "status": random.choice(["lead", "prospect", "customer"]),
                    "source": random.choice(
                        ["Website", "Referral", "Cold Call", "Email Campaign"]
                    ),
                },
            )
            contacts.append(contact)

        # Create sample deals
        deal_names = [
            "Enterprise Software License",
            "Cloud Migration Project",
            "Data Analytics Platform",
            "Marketing Automation Suite",
            "Customer Support System",
            "Mobile App Development",
            "API Integration Services",
            "Security Audit Contract",
        ]

        deals = []
        for i, deal_name in enumerate(deal_names):
            contact = random.choice(contacts)
            deal, created = Deal.objects.get_or_create(
                name=deal_name,
                defaults={
                    "contact": contact,
                    "company": contact.company,
                    "amount": random.randint(10000, 500000),
                    "stage": random.choice(
                        [
                            "prospecting",
                            "qualification",
                            "proposal",
                            "negotiation",
                            "closed_won",
                        ]
                    ),
                    "probability": random.randint(10, 90),
                    "priority": random.choice(["low", "medium", "high"]),
                    "expected_close_date": timezone.now().date()
                    + timedelta(days=random.randint(1, 90)),
                    "owner": user,
                    "description": f"Deal for {deal_name} with {contact.company.name}",
                },
            )
            deals.append(deal)

        # Create sample activities
        activity_types = ["call", "email", "meeting", "task", "note", "demo"]
        activity_subjects = [
            "Initial discovery call",
            "Product demonstration",
            "Follow-up email",
            "Contract review meeting",
            "Technical requirements discussion",
            "Pricing negotiation",
            "Implementation planning",
            "Stakeholder introduction",
        ]

        for i in range(20):
            contact = random.choice(contacts)
            activity_type = random.choice(activity_types)
            subject = random.choice(activity_subjects)

            Activity.objects.get_or_create(
                subject=f"{subject} - {contact.company.name}",
                defaults={
                    "activity_type": activity_type,
                    "contact": contact,
                    "company": contact.company,
                    "deal": random.choice(deals) if random.random() > 0.5 else None,
                    "owner": user,
                    "status": random.choice(["pending", "completed"]),
                    "due_date": timezone.now() + timedelta(days=random.randint(-7, 30)),
                    "description": f"Activity related to {subject}",
                    "duration_minutes": (
                        random.randint(15, 120)
                        if activity_type in ["call", "meeting"]
                        else None
                    ),
                },
            )

        # Create sample tags
        tag_names = [
            "Hot Lead",
            "Enterprise",
            "SMB",
            "Follow-up Required",
            "Technical",
            "Decision Maker",
        ]
        tags = []
        for tag_name in tag_names:
            tag, created = Tag.objects.get_or_create(
                name=tag_name,
                defaults={
                    "color": random.choice(
                        ["#18B0FF", "#7B68EE", "#00D4AA", "#FF9500", "#FF3B30"]
                    ),
                    "description": f"Tag for {tag_name}",
                },
            )
            tags.append(tag)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created:\n"
                f"- {len(companies)} companies\n"
                f"- {len(contacts)} contacts\n"
                f"- {len(deals)} deals\n"
                f"- 20 activities\n"
                f"- {len(tags)} tags\n"
                f"- 1 admin user (username: admin, password: admin123)"
            )
        )
