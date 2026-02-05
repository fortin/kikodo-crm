import csv
import io
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.signing import Signer
from django.db import transaction
from django.utils import timezone

from .models import (
    Activity,
    Company,
    Contact,
    Deal,
    OperatingArea,
    PainSignal,
    PainType,
    SequenceEnrollment,
    SequenceStep,
)


class ColumnMapper:
    """Maps CSV columns to model fields using fuzzy matching and transformations."""

    # Field aliases - maps CSV column names to model field names
    CONTACT_FIELD_ALIASES = {
        "first_name": ["first_name", "firstname", "fname", "given_name"],
        "last_name": ["last_name", "lastname", "lname", "surname", "family_name"],
        "full_name": [
            "full_name",
            "fullname",
            "complete_name",
        ],  # Note: NOT "name" to avoid company_name
        "email": ["email", "email_address", "e_mail", "mail"],  # Note: NOT email_status
        "phone": [
            "phone",
            "phone_number",
            "phone_number_1",
            "telephone",
            "tel",
            "phone_1",
        ],
        "mobile": [
            "mobile",
            "mobile_phone",
            "cell",
            "cell_phone",
            "phone_number_2",
            "phone_2",
        ],
        "job_title": [
            "job_title",
            "position",
            "title",
            "current_position_1",
            "current_position",
            "role",
            "job",
        ],
        "department": ["department", "dept", "division"],
        "linkedin": [
            "linkedin",
            "linkedin_url",
            "linkedin_profile",
            "linkedin_link",
        ],
        "twitter_handle": ["twitter", "twitter_handle", "twitter_username"],
        "address": ["address", "street_address", "street"],
        "city": [
            "city",
            "company_city_1",
        ],  # Note: "location" is parsed separately, not mapped to city
        "state": ["state", "province", "region"],
        "country": ["country", "nation"],
        "location": [
            "location"
        ],  # Special field that gets parsed into city, state, country
        "postal_code": ["postal_code", "zip", "zip_code", "postcode"],
        "headline": ["headline", "tagline", "professional_headline"],
        "bio": ["about", "bio", "biography", "description", "summary"],
        "skills": ["skills", "competencies", "expertise"],
        "birthday": ["birthday", "date_of_birth", "dob", "birth_date"],
        "pronouns": ["pronouns", "pronoun"],
        "latest_post": ["latest_post", "last_post", "most_recent_post", "recent_post"],
        "notes": ["notes", "note", "comments", "remarks"],
        "outreach_status": [
            "outreach_status",
            "outreach",
            "outreach status",
            "contact_status",
        ],
        "verified": ["verified", "contact_verified", "verified_contact"],
    }

    COMPANY_FIELD_ALIASES = {
        "name": [
            "company_name",
            "name",
            "company",
            "organization",
            "org_name",
        ],  # Map company name fields
        "industry": [
            "industry",
            "company_industry_1",
            "company_industry_2",
            "company_industry_3",
            "company_industry",
            "sector",
            "business_industry",
        ],
        "website": [
            "website",
            "company_domain",
            "domain",
            "web",
            "website_1",
            "company_website",
        ],
        "linkedin_url": [
            "company_link",
            "linkedin",
            "linkedin_url",
            "company_linkedin",
            "linkedin_company",
        ],
        "phone": ["phone", "company_phone", "telephone", "tel", "phone_number"],
        "email": [
            "company_email",
        ],  # Note: NOT "contact_email" or just "email" to avoid contact emails
        "address": ["address", "company_address", "street_address", "street"],
        "city": [
            "city",
            "company_city_1",
            "company_city_2",
            "company_city_3",
        ],
        "state": ["state", "province", "region"],
        "country": ["country", "nation"],
        "postal_code": ["postal_code", "company_postal_code", "zip", "zip_code"],
        "description": [
            "description",
            "company_about",
            "about",
            "company_description",
            "bio",
        ],
        "annual_revenue": ["annual_revenue", "revenue", "annual_revenue_amount"],
        "employee_count": [
            "employee_count",
            "company_size",
            "employees",
            "size",
            "headcount",
        ],
        "founded_year": [
            "founded_year",
            "company_founded",
            "founded",
            "year_founded",
            "establishment_year",
        ],
        "size_category": ["size_category", "company_size_category", "size_category"],
        "specialties": ["specialties", "company_specialties", "specialty"],
        "facility_count": [
            "facility_count",
            "facilities",
            "num_facilities",
            "number_of_facilities",
            "facility_count",
        ],
        "priority_tier": [
            "priority_tier",
            "tier",
            "priority",
            "priority tier",
        ],
        # logo_url / company_logo not imported (often long CDN URLs; not needed)
    }

    def __init__(self):
        self.contact_mappings = {}
        self.company_mappings = {}

    def normalize_column_name(self, column_name: str) -> str:
        """Normalize column name for matching."""
        if not column_name:
            return ""
        # Convert to lowercase, replace spaces/hyphens with underscores
        normalized = column_name.lower().strip()
        normalized = re.sub(r"[-\s]+", "_", normalized)
        normalized = re.sub(r"[^\w_]", "", normalized)
        return normalized

    def find_best_match(
        self, column_name: str, field_aliases: Dict[str, List[str]]
    ) -> Optional[str]:
        """Find the best matching model field for a CSV column."""
        normalized = self.normalize_column_name(column_name)

        # Exclude columns that never map to our Company/Contact model fields
        excluded_patterns = [
            "email_status",
            "filtered",
            "open",
            "premium",
            "open_to_work",
            "changed_job",
            "domain_status",
            "filter_message",
            "num_of_connections",
            "company_id",  # LinkedIn company IDs, not a name
            "salesnav_leads_url",
            "sales_navigator",
            "account_url",
            "alexa_ranking",
            "crunchbase_url",
            "market_cap",
            "technologies",  # not a Company field
            "keywords",  # not a Company field
            "company_location",  # parsed separately into city/state/country
            "location",  # generic location handled separately
            "time_in_position",
            "time_in_company",
            "company_name",  # only map to company name, not contact names (handled below)
            "job_details",
            "headline",
        ]
        if any(pattern in normalized for pattern in excluded_patterns):
            return None

        # Prevent wrong mappings - industry should NOT map to city or names
        if normalized == "industry" or normalized.startswith("company_industry"):
            # Only map to industry field, not city or names
            if "industry" in [f for f in field_aliases.keys()]:
                return "industry"
            return None

        # Allow company_specialties/specialties to map to company specialties only
        if normalized in ["specialties", "company_specialties"]:
            if "specialties" in field_aliases:
                return "specialties"
            return None
        if normalized in ["technologies", "keywords"]:
            return None

        # Prevent time duration fields from mapping to company name
        if normalized in [
            "time_in_position",
            "time_in_company",
            "time_in_position_1",
            "time_in_company_1",
        ]:
            return None

        # Prevent company domain/website from mapping to city
        if normalized in [
            "company_domain",
            "company_website",
            "website_1",
            "website_2",
            "website_3",
        ]:
            # Only allow mapping to website field, not city
            if "website" in [f for f in field_aliases.keys()]:
                return "website"
            return None

        # Prevent company_name from mapping to first_name/last_name
        if normalized == "company_name" or normalized.startswith("company_name"):
            # Only allow mapping to company name field, not contact names
            if "name" in [f for f in field_aliases.keys()] and "company" in [
                f for f in field_aliases.keys()
            ]:
                # This is for company mapping, allow it
                pass
            elif "first_name" in [f for f in field_aliases.keys()] or "last_name" in [
                f for f in field_aliases.keys()
            ]:
                # Don't allow company_name to map to contact name fields
                return None

        # Prevent contact name fields from mapping to company name
        if normalized in ["first_name", "last_name", "full_name"]:
            # Don't allow contact name fields to map to company name
            if "name" in [f for f in field_aliases.keys()] and "company" in [
                f for f in field_aliases.keys()
            ]:
                # This is trying to map to company name, reject it
                return None

        # Don't map "Company" column to contact fields (e.g. city via company_city_1)
        if normalized == "company" and "city" in field_aliases:
            return None

        # Prevent long text fields from mapping to job_title (contact only)
        if normalized in ["job_details", "about", "bio"]:
            if "job_title" in field_aliases:
                return None

        # Prevent location fields from mapping to company name or contact names
        if normalized.startswith("company_location") or normalized == "location":
            # Only allow mapping to location field for contacts, not to names
            if (
                "location" in [f for f in field_aliases.keys()]
                and "company" not in normalized
            ):
                return "location"
            return None

        # Prevent company_link from mapping to name or website.
        # "linkedin" = contact profile → field "linkedin". "company_link" / "company_linkedin" = company page → "linkedin_url".
        if normalized in ["company_link", "linkedin", "company_linkedin"]:
            if "linkedin_url" in field_aliases:
                return "linkedin_url"
            if "linkedin" in field_aliases:
                # Only map explicitly contact-style columns to contact linkedin; never company_link
                if normalized == "company_link":
                    return None
                return "linkedin"
            return None

        # Prevent numeric-only columns from mapping to email or name
        if normalized.endswith("_connections") or normalized.startswith("num_"):
            return None

        # Prevent URLs from mapping to name field
        if "linkedin.com" in column_name.lower() or column_name.lower().startswith(
            "http"
        ):
            if "linkedin_url" in [f for f in field_aliases.keys()]:
                return "linkedin_url"
            return None

        # Prevent name fields from mapping if the column contains location indicators
        if any(
            indicator in normalized
            for indicator in ["location", "city", "state", "country", "address"]
        ):
            # Only allow if it's explicitly a name-related field
            if normalized not in [
                "first_name",
                "last_name",
                "full_name",
                "name",
                "company_name",
            ]:
                # Don't map location-related columns to name fields
                if (
                    "first_name" in [f for f in field_aliases.keys()]
                    or "last_name" in [f for f in field_aliases.keys()]
                    or "name" in [f for f in field_aliases.keys()]
                ):
                    # Check if this is trying to map to a name field
                    for field in ["first_name", "last_name", "full_name", "name"]:
                        if field in field_aliases:
                            # Don't allow location columns to map to name fields
                            return None

        # First, try exact match
        for field, aliases in field_aliases.items():
            if normalized in [self.normalize_column_name(a) for a in aliases]:
                return field

        # Try partial matching (contains) - but be more strict
        for field, aliases in field_aliases.items():
            for alias in aliases:
                alias_norm = self.normalize_column_name(alias)
                # Only match if one is contained in the other (not just partial overlap)
                if (
                    alias_norm == normalized
                    or (len(alias_norm) > 3 and alias_norm in normalized)
                    or (len(normalized) > 3 and normalized in alias_norm)
                ):
                    return field

        # Try fuzzy matching with similarity - but require higher threshold
        best_match = None
        best_score = 0

        for field, aliases in field_aliases.items():
            for alias in aliases:
                alias_norm = self.normalize_column_name(alias)
                # Simple similarity: count common characters
                common = len(set(normalized) & set(alias_norm))
                total = len(set(normalized) | set(alias_norm))
                if total > 0:
                    score = common / total
                    # Require higher similarity (70%) and minimum length
                    if (
                        score > best_score
                        and score > 0.7
                        and len(normalized) >= 3
                        and len(alias_norm) >= 3
                    ):
                        best_score = score
                        best_match = field

        return best_match

    def map_columns(
        self, csv_columns: List[str]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Map CSV columns to Contact and Company model fields."""
        contact_mappings = {}
        company_mappings = {}

        for col in csv_columns:
            # Try to match to contact fields
            contact_field = self.find_best_match(col, self.CONTACT_FIELD_ALIASES)
            if contact_field:
                contact_mappings[col] = contact_field

            # Try to match to company fields
            company_field = self.find_best_match(col, self.COMPANY_FIELD_ALIASES)
            if company_field:
                company_mappings[col] = company_field

        return contact_mappings, company_mappings


class FieldParser:
    """Parses and transforms field values from CSV."""

    @staticmethod
    def split_name(full_name: str) -> Tuple[str, str]:
        """Split full name into first and last name, preserving prefixes."""
        if not full_name or not full_name.strip():
            return "", ""

        # Common name prefixes that should be preserved in last name
        prefixes = [
            "ó",
            "o'",
            "o",
            "van",
            "von",
            "de",
            "del",
            "della",
            "di",
            "da",
            "du",
            "le",
            "la",
            "les",
            "mac",
            "mc",
            "fitz",
            "st",
            "saint",
            "san",
            "santa",
        ]

        parts = full_name.strip().split(",", 1)
        if len(parts) == 2:
            # Could be "Last, First" format (e.g., "Ó Dúláin, Máirtín")
            # OR "First Last, Degree" format (e.g., "Anissa Perkins, MA")
            # Check if second part looks like a degree (short, uppercase, common degree abbreviations)
            second_part = parts[1].strip()
            degree_pattern = r"^(MA|MBA|PhD|MD|JD|LLM|MS|MSc|BS|BA|BSc|BA|EdD|DDS|DVM|RN|LPN|CPA|CFA|PMP|PMI|CCNA|AWS|GCP|Azure)$"
            if re.match(degree_pattern, second_part, re.IGNORECASE):
                # This is "First Last, Degree" format - ignore the degree
                full_name = parts[0].strip()  # Use only the name part
                # Now process as "First Last" format
                name_parts = full_name.strip().split()
                # Continue processing below
            else:
                # "Last, First" format (e.g., "Ó Dúláin, Máirtín")
                last_name = parts[0].strip()
                first_name = parts[1].strip()
                # Remove suffixes like "MA", "Jr.", etc. from first name
                first_name = re.sub(
                    r"\s+(MA|Jr\.?|Sr\.?|III|II|IV)$",
                    "",
                    first_name,
                    flags=re.IGNORECASE,
                )
                return first_name, last_name

        # "First Last" format (e.g., "Máirtín Ó Dúláin" or "Anissa Perkins" after removing degree)
        # If we already processed a degree, name_parts is set above
        if "name_parts" not in locals():
            name_parts = full_name.strip().split()

        if len(name_parts) >= 2:
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                remaining_parts = name_parts[1:]

                # Check if second part is a prefix (case-insensitive)
                if remaining_parts:
                    second_word = remaining_parts[0]  # Keep original case for "Ó"
                    second_word_lower = second_word.lower()
                    # Check for exact prefix matches (with or without apostrophe)
                    prefix_found = False
                    for prefix in prefixes:
                        # Handle variations like "o'" vs "o" vs "ó"
                        # Normalize both for comparison but preserve original
                        prefix_normalized = (
                            prefix.lower().replace("'", "").replace("ó", "o")
                        )
                        second_normalized = second_word_lower.replace("'", "").replace(
                            "ó", "o"
                        )
                        # Check exact match or starts with
                        if (
                            second_normalized == prefix_normalized
                            or second_word_lower == prefix.lower()
                            or second_word_lower.startswith(prefix.lower())
                        ):
                            prefix_found = True
                            break

                    if prefix_found:
                        # Include prefix and all following parts in last name
                        # This preserves "Ó Dúláin" as the last name
                        # Use original case from remaining_parts to preserve "Ó"
                        last_name = " ".join(remaining_parts)
                    else:
                        # Regular case: all remaining parts are last name
                        last_name = " ".join(remaining_parts)
                else:
                    last_name = ""
                return first_name, last_name
            elif len(name_parts) == 1:
                return name_parts[0], ""
            else:
                return "", ""

    @staticmethod
    def parse_location(location: str) -> Dict[str, str]:
        """Parse location string into city, state, country."""
        if not location or not location.strip():
            return {}

        parts = [p.strip() for p in location.split(",")]
        result = {}

        if len(parts) >= 1:
            result["city"] = parts[0]
        if len(parts) >= 2:
            result["state"] = parts[1]
        if len(parts) >= 3:
            result["country"] = parts[2]
        elif len(parts) == 2:
            # Could be city, country or city, state
            # Assume second is country if it's a common country name
            common_countries = [
                "united states",
                "usa",
                "canada",
                "uk",
                "united kingdom",
                "australia",
                "germany",
                "france",
                "spain",
                "italy",
            ]
            if parts[1].lower() in common_countries:
                result["country"] = parts[1]
            else:
                result["state"] = parts[1]

        return result

    @staticmethod
    def parse_company_size(size_str: str) -> Optional[int]:
        """Parse company size string to integer."""
        if not size_str or not size_str.strip():
            return None

        size_str = size_str.strip()

        # Handle "10000+" format
        if size_str.endswith("+"):
            try:
                return int(size_str[:-1])
            except ValueError:
                pass

        # Handle "500-1000" format - take average
        if "-" in size_str:
            try:
                parts = size_str.split("-")
                if len(parts) == 2:
                    low = int(parts[0].strip())
                    high = int(parts[1].strip())
                    return (low + high) // 2
            except ValueError:
                pass

        # Handle "Self-employed" or similar
        if "self" in size_str.lower() or "individual" in size_str.lower():
            return 1

        # Try to extract number
        numbers = re.findall(r"\d+", size_str.replace(",", ""))
        if numbers:
            try:
                return int(numbers[-1])  # Take the last/largest number
            except ValueError:
                pass

        return None

    @staticmethod
    def parse_revenue(revenue_str: str) -> Optional[Decimal]:
        """Parse revenue string to Decimal."""
        if not revenue_str or not revenue_str.strip():
            return None

        revenue_str = revenue_str.strip().upper()

        # Skip if it's just a small number (likely a ranking, not revenue)
        # Remove currency symbols and commas first to check
        revenue_clean = re.sub(r"[$,\s]", "", revenue_str)
        if revenue_clean.isdigit() and int(revenue_clean) < 10000:
            return None

        # Remove currency symbols and commas
        revenue_str = re.sub(r"[$,\s]", "", revenue_str)

        multiplier = 1
        if revenue_str.endswith("M"):
            multiplier = 1000000
            revenue_str = revenue_str[:-1]
        elif revenue_str.endswith("B"):
            multiplier = 1000000000
            revenue_str = revenue_str[:-1]
        elif revenue_str.endswith("K"):
            multiplier = 1000
            revenue_str = revenue_str[:-1]

        try:
            value = Decimal(revenue_str) * multiplier
            # Additional validation: revenue should be substantial
            if value < 1000:  # Less than $1000 is probably not revenue
                return None
            return value
        except (ValueError, InvalidOperation):
            return None

    @staticmethod
    def parse_year(year_str: str) -> Optional[int]:
        """Parse year from various formats."""
        if not year_str or not year_str.strip():
            return None

        year_str = year_str.strip()

        # Try to extract 4-digit year
        year_match = re.search(r"\b(19|20)\d{2}\b", year_str)
        if year_match:
            try:
                return int(year_match.group())
            except ValueError:
                pass

        # Try direct integer conversion
        try:
            year = int(year_str)
            if 1800 <= year <= 2100:  # Reasonable range
                return year
        except ValueError:
            pass

        return None

    @staticmethod
    def normalize_url(url_str: str) -> str:
        """Normalize URL - add protocol if missing."""
        if not url_str or not url_str.strip():
            return ""

        url_str = url_str.strip()

        # If it's just a domain, add https://
        if not url_str.startswith(("http://", "https://")):
            if "." in url_str and " " not in url_str:
                url_str = "https://" + url_str

        return url_str

    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """Parse date from various formats."""
        if not date_str or not date_str.strip():
            return None

        date_str = date_str.strip()

        # Common date and datetime formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y-%m",
            "%m/%Y",
            "%Y",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt
            except ValueError:
                continue

        return None


class CSVImporter:
    """Handles CSV import for Contacts and Companies."""

    def __init__(
        self,
        user: User,
        create_companies: bool = True,
        update_existing: bool = False,
        import_type: str = "both",
    ):
        self.user = user
        self.create_companies = create_companies
        self.update_existing = update_existing
        self.import_type = import_type  # 'contacts', 'companies', or 'both'
        self.mapper = ColumnMapper()
        self.parser = FieldParser()
        self._contact_name_lookup = (
            None  # built lazily for update_existing + no-email matching
        )
        self.errors = []
        self.warnings = []
        self.stats = {
            "contacts_created": 0,
            "contacts_updated": 0,
            "companies_created": 0,
            "companies_updated": 0,
            "rows_processed": 0,
            "rows_failed": 0,
        }

    @staticmethod
    def _normalized_contact_name(first: str, last: str) -> str:
        """Same logic as delete_duplicate_contacts_empty_title: match regardless of first/last split."""
        f = (first or "").strip()
        l = (last or "").strip()
        return " ".join((f + " " + l).split()).lower()

    def _get_contact_name_lookup(self):
        """Build lookup of active contacts by normalized name for update_existing when row has no email."""
        if self._contact_name_lookup is not None:
            return self._contact_name_lookup
        from collections import defaultdict

        self._contact_name_lookup = defaultdict(list)
        for c in Contact.objects.filter(is_active=True).only(
            "id", "first_name", "last_name", "company_id"
        ):
            key = self._normalized_contact_name(c.first_name, c.last_name)
            if key:
                self._contact_name_lookup[key].append((c.company_id, c))
        return self._contact_name_lookup

    def import_csv(self, csv_file) -> Dict[str, Any]:
        """Import CSV file and return statistics."""
        self._contact_name_lookup = (
            None  # rebuild per run for update_existing name matching
        )
        try:
            # Read CSV content
            if hasattr(csv_file, "read"):
                # Reset file pointer if it's a file object
                if hasattr(csv_file, "seek"):
                    csv_file.seek(0)
                content = csv_file.read()
                if isinstance(content, bytes):
                    # Try UTF-8 first, then fall back to other encodings
                    try:
                        content = content.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            content = content.decode("latin-1")
                        except UnicodeDecodeError:
                            content = content.decode("utf-8", errors="ignore")
            else:
                content = csv_file

            # Use csv.DictReader with proper quoting to handle commas in quoted fields
            # QUOTE_MINIMAL allows proper parsing of quoted fields with commas
            csv_reader = csv.DictReader(
                io.StringIO(content),
                quoting=csv.QUOTE_MINIMAL,
                skipinitialspace=True,
                escapechar="\\",  # Handle escaped quotes
            )
            columns = csv_reader.fieldnames

            if not columns:
                raise ValueError("CSV file has no headers")

            # Map columns to fields
            contact_mappings, company_mappings = self.mapper.map_columns(columns)

            # Log mapping info for debugging
            if not contact_mappings and not company_mappings:
                raise ValueError(
                    f"Could not map any CSV columns to model fields. "
                    f"Available columns: {', '.join(columns[:20])}"  # Show first 20 columns
                )

            if self.import_type in ["contacts", "both"] and not contact_mappings:
                self.warnings.append(
                    f"No contact fields found in CSV. Found {len(columns)} columns. "
                    f"Sample columns: {', '.join(columns[:10])}"
                )

            if self.import_type in ["companies", "both"] and not company_mappings:
                self.warnings.append(
                    f"No company fields found in CSV. Found {len(columns)} columns. "
                    f"Sample columns: {', '.join(columns[:10])}"
                )

            # Debug: log what mappings were found (only if verbose or if no mappings found)
            # This will help diagnose issues but won't clutter normal imports

            # Process rows
            row_count = 0
            with transaction.atomic():
                for row_num, row in enumerate(
                    csv_reader, start=2
                ):  # Start at 2 (header is row 1)
                    row_count += 1
                    try:
                        self._process_row(
                            row, contact_mappings, company_mappings, row_num
                        )
                        self.stats["rows_processed"] += 1
                    except Exception as e:
                        self.stats["rows_failed"] += 1
                        self.errors.append(f"Row {row_num}: {str(e)}")

            if row_count == 0:
                self.warnings.append("CSV file contains no data rows (only headers)")

            return {
                "success": True,
                "stats": self.stats,
                "errors": self.errors,
                "warnings": self.warnings,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stats": self.stats,
                "errors": self.errors,
                "warnings": self.warnings,
            }

    def _process_row(
        self,
        row: Dict[str, str],
        contact_mappings: Dict[str, str],
        company_mappings: Dict[str, str],
        row_num: int,
    ):
        """Process a single CSV row."""
        # Extract company data first
        company_data = {}
        company = None

        # Create companies if:
        # 1. Import type includes companies (companies or both), OR
        # 2. Import type is contacts but create_companies is True
        should_create_companies = (self.import_type in ["companies", "both"]) or (
            self.import_type == "contacts" and self.create_companies
        )

        if should_create_companies:
            # Process company_location field separately (if it exists) before other mappings
            # This ensures location parsing happens before city/state/country get overwritten
            # Check for company_location_1, company_location_2, company_location_3, etc.
            company_location_value = None
            for col in row.keys():
                col_lower = col.lower()
                # Match "company_location" columns (company_location_1, company_location_2, etc.)
                if (
                    col_lower.startswith("company_location")
                    or col_lower == "company_location"
                ):
                    if (
                        row[col]
                        and row[col].strip()
                        and row[col].strip().lower()
                        not in ["false", "true", "null", "none"]
                    ):
                        # Use the first non-empty company_location found
                        company_location_value = row[col].strip()
                        break

            if company_location_value:
                location_data = self.parser.parse_location(company_location_value)
                # Update city, state, country from parsed location
                # This will be used unless explicitly overridden by other mapped fields
                for loc_field, loc_value in location_data.items():
                    if loc_value:  # Only set if we got a value
                        # Don't overwrite if already set from other fields (unless it's empty)
                        if loc_field not in company_data or not company_data[loc_field]:
                            # Truncate location fields to model max_length
                            loc_value = self._truncate_field_value(
                                loc_field, loc_value, Company
                            )
                            company_data[loc_field] = loc_value

        if should_create_companies:
            # 1) Resolve company name from row (support "Company", "company_name", etc. via normalized match)
            explicit_company_name = ""
            company_name_cols = ["company", "company_name", "organization", "org_name"]
            for col in row.keys():
                if not col or not row.get(col):
                    continue
                if self.mapper.normalize_column_name(col) in company_name_cols:
                    explicit_company_name = row[col].strip()
                    break

            if explicit_company_name:
                # Minimal validation: skip obvious garbage (URLs or pure numbers)
                if (
                    not explicit_company_name.startswith(
                        ("http://", "https://", "www.")
                    )
                    and not explicit_company_name.isdigit()
                ):
                    company_data["name"] = self._truncate_field_value(
                        "name", explicit_company_name, Company
                    )

            # 2) Use mapped company fields if we have them for supplemental data
            if company_mappings:
                for csv_col, model_field in company_mappings.items():
                    value = row.get(csv_col, "").strip()

                    # Skip empty values and boolean values
                    if not value or value.lower() in ["false", "true", "null", "none"]:
                        continue

                    # Apply field-specific parsing and validation
                    if model_field == "industry" and model_field in company_data:
                        # Prefer first non-empty industry (e.g. company_industry_1 over 2/3)
                        continue
                    if model_field == "name":
                        # We already set name from explicit company_name/company above.
                        # Never override that here; just skip.
                        if "name" in company_data:
                            continue
                        # As a fallback (if explicit name was missing), accept only
                        # basic, non-garbage values from clearly company-related columns.
                        if value.startswith(("http://", "https://", "www.")):
                            continue
                        if value.isdigit():
                            continue
                        if "linkedin.com" in value.lower():
                            continue
                        if "company" not in csv_col.lower():
                            continue
                        value = self._truncate_field_value(model_field, value, Company)
                        company_data[model_field] = value
                    elif model_field == "website":
                        value = self.parser.normalize_url(value)
                        value = self._truncate_field_value(model_field, value, Company)
                        company_data[model_field] = value
                    elif model_field == "linkedin_url":
                        # Ensure LinkedIn URLs are properly formatted
                        if not value.startswith(("http://", "https://")):
                            if "linkedin.com" in value:
                                value = "https://" + value.lstrip("/")
                            else:
                                # Skip if it doesn't look like a LinkedIn URL
                                continue
                        value = self._truncate_field_value(model_field, value, Company)
                        company_data[model_field] = value
                    elif model_field == "employee_count":
                        value = self.parser.parse_company_size(value)
                        if value is not None:
                            company_data[model_field] = value
                    elif model_field == "annual_revenue":
                        # Only parse if it looks like revenue (has currency symbols, M/B/K, or is a large number)
                        # Skip small numbers that might be rankings or IDs
                        value_clean = (
                            value.replace("$", "").replace(",", "").strip().upper()
                        )
                        # Skip if it's just a small number (likely a ranking, not revenue)
                        if value_clean.isdigit() and int(value_clean) < 10000:
                            continue
                        parsed_value = self.parser.parse_revenue(value)
                        if parsed_value is not None:
                            company_data[model_field] = parsed_value
                    elif model_field == "founded_year":
                        value = self.parser.parse_year(value)
                        if value is not None:
                            company_data[model_field] = value
                    elif model_field == "email":
                        # Only set email if it's actually an email address
                        # Skip if it's just a number (like "1270")
                        if value.isdigit():
                            continue
                        if "@" not in value or value.lower() in [
                            "verified",
                            "unknown",
                            "unverified",
                        ]:
                            continue
                        # Additional check: skip if the column name suggests it's a contact email
                        csv_col_lower = csv_col.lower()
                        if (
                            "contact" in csv_col_lower
                            and "company" not in csv_col_lower
                        ):
                            # This is likely a contact email, not a company email
                            continue
                        value = self._truncate_field_value(model_field, value, Company)
                        company_data[model_field] = value
                    elif model_field in ["city", "state", "country"]:
                        # Prefer first non-empty (e.g. company_city_1 over 2/3)
                        if model_field in company_data and company_data[model_field]:
                            continue
                        # Skip if this came from company_location (already processed above)
                        if not csv_col.lower().startswith("company_location"):
                            # Check if it looks like a website/domain (shouldn't be in city)
                            if self._looks_like_website(value):
                                continue
                            # Check if column name suggests it's a website/domain
                            if any(
                                indicator in csv_col.lower()
                                for indicator in ["domain", "website", "url"]
                            ):
                                continue
                            # This is from a different column, so use it
                            value = self._truncate_field_value(
                                model_field, value, Company
                            )
                            company_data[model_field] = value
                        # If it's from company_location, we already processed it above, so skip
                    elif model_field == "facility_count":
                        try:
                            n = int(value.strip())
                            if n >= 0:
                                company_data[model_field] = n
                        except (ValueError, TypeError):
                            pass
                    elif model_field == "priority_tier":
                        v = value.strip().lower()
                        if v in ("1", "tier 1", "tier1"):
                            company_data[model_field] = 1
                        elif v in ("2", "tier 2", "tier2"):
                            company_data[model_field] = 2
                        elif v in ("3", "tier 3", "tier3"):
                            company_data[model_field] = 3
                    else:
                        # Skip numeric-only values for text fields
                        if model_field not in [
                            "employee_count",
                            "annual_revenue",
                            "founded_year",
                            "facility_count",
                            "priority_tier",
                        ]:
                            if value.isdigit() and len(value) > 3:
                                continue
                        # Truncate string fields to model max_length
                        value = self._truncate_field_value(model_field, value, Company)
                        company_data[model_field] = value

            # Fallback: if website/email not set via mappings, try explicit company columns
            # This ensures we still pick up obvious company fields even if mapping failed
            if "website" not in company_data:
                for col in [
                    "company_domain",
                    "website_1",
                    "website",
                    "company_website",
                ]:
                    raw = row.get(col, "").strip()
                    if raw:
                        if not self._looks_like_website(raw):
                            continue
                        website = self.parser.normalize_url(raw)
                        website = self._truncate_field_value(
                            "website", website, Company
                        )
                        company_data["website"] = website
                        break

            if "email" not in company_data:
                # Collect any obvious lead/contact emails in this row so we can avoid
                # re-using them as the company email.
                possible_lead_emails = set()
                for lead_col in ["email", "email_address", "e_mail", "mail"]:
                    lead_raw = row.get(lead_col, "").strip()
                    if lead_raw and "@" in lead_raw:
                        possible_lead_emails.add(lead_raw.lower())

                for col in ["company_email"]:
                    raw = row.get(col, "").strip()
                    if (
                        raw
                        and "@" in raw
                        and raw.lower()
                        not in [
                            "verified",
                            "unknown",
                            "unverified",
                        ]
                    ):
                        # Skip if it's clearly a number
                        if raw.isdigit():
                            continue
                        # Skip if this matches one of the lead/contact emails on the same row
                        if raw.lower() in possible_lead_emails:
                            continue
                        email_val = self._truncate_field_value("email", raw, Company)
                        company_data["email"] = email_val
                        break

            # 3) Create or get company if we have a name
            # Ensure we're using company_name from CSV (or a very small fallback), not random fields
            company_name = company_data.get("name", "").strip()

            # If name is missing but we have other data, try to get it from the row by normalized column name
            # (handles "Company", "Company Name", etc. regardless of header casing)
            if not company_name:
                for col in row.keys():
                    if not col or not row.get(col):
                        continue
                    col_norm = self.mapper.normalize_column_name(col)
                    if col_norm not in [
                        "company",
                        "company_name",
                        "organization",
                        "org_name",
                    ]:
                        continue
                    if (
                        "location" in col_norm
                        or "duration" in col_norm
                        or "time_in" in col_norm
                    ):
                        continue
                    if any(x in col_norm for x in ["domain", "website", "url", "link"]):
                        continue
                    potential_name = row[col].strip()
                    if (
                        potential_name
                        and not potential_name.startswith(
                            ("http://", "https://", "www.")
                        )
                        and not potential_name.isdigit()
                        and "linkedin.com" not in potential_name.lower()
                        and not self._looks_like_location(potential_name)
                        and not self._looks_like_duration(potential_name)
                        and not self._looks_like_person_name(potential_name)
                    ):
                        company_name = potential_name
                        company_data["name"] = company_name
                        break

            # Final validation - company name must be valid
            if company_name:
                # Normalize whitespace to avoid duplicate companies ("A  B" vs "A B")
                company_name = " ".join(company_name.split())
                company_data["name"] = company_name
                # Skip if it looks like a URL
                if (
                    company_name.startswith(("http://", "https://", "www."))
                    or "linkedin.com" in company_name.lower()
                ):
                    company_name = ""
                    company_data.pop("name", None)
                # Skip if it's just a number
                elif company_name.isdigit():
                    company_name = ""
                    company_data.pop("name", None)
                # Skip if it looks like a location
                elif self._looks_like_location(company_name):
                    company_name = ""
                    company_data.pop("name", None)
                # Skip if it looks like a duration
                elif self._looks_like_duration(company_name):
                    company_name = ""
                    company_data.pop("name", None)

            if company_name:
                company, created = Company.objects.get_or_create(
                    name=company_name, defaults={**company_data, "owner": self.user}
                )
                if created:
                    self.stats["companies_created"] += 1
                elif self.update_existing:
                    for key, value in company_data.items():
                        if key != "name":  # Don't update name
                            # Truncate string values before setting
                            if isinstance(value, str):
                                value = self._truncate_field_value(key, value, Company)
                            setattr(company, key, value)
                    company.save()
                    self.stats["companies_updated"] += 1

                # Populate State(s) from parsed company_location (e.g. "Burbank, California, United States")
                if company.state:
                    val = company.state[:100]
                    OperatingArea.objects.get_or_create(
                        company=company,
                        kind="state",
                        value=val,
                        defaults={"code": val[:50] if len(val) > 50 else val},
                    )
                if company.country:
                    val = company.country[:100]
                    OperatingArea.objects.get_or_create(
                        company=company,
                        kind="country",
                        value=val,
                        defaults={"code": val[:50] if len(val) > 50 else val},
                    )

                # State(s) / operating areas: look for "states", "state(s)", "operating_states" column
                for col in row.keys():
                    if not col or not row.get(col):
                        continue
                    col_norm = self.mapper.normalize_column_name(col)
                    if col_norm not in (
                        "states",
                        "state_s",
                        "operating_states",
                        "operating_areas",
                    ):
                        continue
                    raw = row[col].strip()
                    if not raw or raw.lower() in ("false", "true", "null", "none"):
                        continue
                    for part in (p.strip() for p in raw.split(",") if p.strip()):
                        part = self._truncate_field_value("value", part, OperatingArea)
                        if part:
                            OperatingArea.objects.get_or_create(
                                company=company,
                                kind="state",
                                value=part,
                                defaults={
                                    "code": part[:50] if len(part) > 50 else part
                                },
                            )
                    break

        # Extract contact data
        contact_data = {}

        if self.import_type in ["contacts", "both"]:
            # First, check if full_name exists in row (even if not mapped) and process it first
            # This ensures we get the complete name with prefixes before processing separate columns
            # Priority: full_name column takes precedence over separate first_name/last_name
            full_name_processed = False
            # Check both exact match and case-insensitive match
            for col in row.keys():
                col_lower = col.lower()
                # Only process actual name columns, not location or specialty columns
                if col_lower in ["full_name", "fullname", "complete_name"] or (
                    col_lower == "name"
                    and "company" not in col_lower
                    and "location" not in col_lower
                ):
                    if row[col] and row[col].strip():
                        full_name_value = row[col].strip()
                        # Validate it looks like a name (not a list of specialties, location, etc.)
                        if self._looks_like_name(full_name_value):
                            # Always use full_name if it exists - it has the complete information
                            first_name, last_name = self.parser.split_name(
                                full_name_value
                            )
                            if first_name:
                                first_name = self._truncate_field_value(
                                    "first_name", first_name, Contact
                                )
                                contact_data["first_name"] = first_name
                            if last_name:
                                last_name = self._truncate_field_value(
                                    "last_name", last_name, Contact
                                )
                                contact_data["last_name"] = last_name
                            full_name_processed = True
                            break

            # Process location field separately (if it exists) before other mappings
            # This ensures location parsing happens before city/state/country get overwritten
            # Check both "location" and any column that contains "location" in the name
            location_value = None
            for col in row.keys():
                col_lower = col.lower()
                # Match "location" but not "company_location" (those are for companies)
                if col_lower == "location" or (
                    col_lower.endswith("_location") and "company" not in col_lower
                ):
                    if (
                        row[col]
                        and row[col].strip()
                        and row[col].strip().lower()
                        not in ["false", "true", "null", "none"]
                    ):
                        location_value = row[col].strip()
                        break

            if location_value:
                # Check if it looks like a website/domain (shouldn't be parsed as location)
                if not self._looks_like_website(location_value):
                    location_data = self.parser.parse_location(location_value)
                    # Update city, state, country from parsed location
                    # This will be used unless explicitly overridden by other mapped fields
                    for loc_field, loc_value in location_data.items():
                        if loc_value:  # Only set if we got a value
                            # Don't overwrite if already set from other fields (unless it's empty)
                            if (
                                loc_field not in contact_data
                                or not contact_data[loc_field]
                            ):
                                # Check if it looks like a website/domain (shouldn't be in city)
                                if loc_field == "city" and self._looks_like_website(
                                    loc_value
                                ):
                                    continue
                                # Truncate location fields to model max_length
                                loc_value = self._truncate_field_value(
                                    loc_field, loc_value, Contact
                                )
                                contact_data[loc_field] = loc_value

            # Now process mapped fields
            for csv_col, model_field in contact_mappings.items():
                value = row.get(csv_col, "").strip()

                # Skip empty values and boolean "false" values that shouldn't be imported
                if not value or value.lower() in ["false", "true", "null", "none"]:
                    continue

                # If full_name was already processed, skip first_name/last_name mappings to prevent overwriting
                if full_name_processed and model_field in ["first_name", "last_name"]:
                    continue

                # Handle special field transformations
                if model_field == "full_name":
                    # Validate it looks like a name before processing
                    if not self._looks_like_name(value):
                        continue
                    # Split full_name into first_name and last_name
                    first_name, last_name = self.parser.split_name(value)
                    # Always use full_name values - they have complete information
                    if first_name:
                        first_name = self._truncate_field_value(
                            "first_name", first_name, Contact
                        )
                        contact_data["first_name"] = first_name
                    if last_name:
                        last_name = self._truncate_field_value(
                            "last_name", last_name, Contact
                        )
                        contact_data["last_name"] = last_name
                elif model_field in ["first_name", "last_name"]:
                    # Validate it looks like a name before assigning
                    if not self._looks_like_name(value):
                        continue
                    # Check if column name suggests it's a company field (shouldn't be in contact names)
                    if "company" in csv_col.lower() and "name" in csv_col.lower():
                        continue
                    # Check if it looks like a company name (shouldn't be in contact names)
                    if self._looks_like_company_name(value):
                        continue
                    # Truncate and assign
                    value = self._truncate_field_value(model_field, value, Contact)
                    contact_data[model_field] = value
                elif model_field == "job_title":
                    # Validate job_title - reject if it's too long (likely wrong data)
                    if len(value) > 200:  # Reasonable max for job title
                        continue
                    # Check if column name suggests it's a long text field
                    if any(
                        indicator in csv_col.lower()
                        for indicator in ["job_details", "about", "bio", "description"]
                    ):
                        continue
                    # Truncate and assign
                    value = self._truncate_field_value(model_field, value, Contact)
                    contact_data[model_field] = value
                elif model_field == "location":
                    # Check if it looks like a website/domain (shouldn't be parsed as location)
                    if self._looks_like_website(value):
                        continue
                    # Parse location into city, state, country
                    location_data = self.parser.parse_location(value)
                    # Only update if not already set
                    for loc_field, loc_value in location_data.items():
                        if loc_field not in contact_data or not contact_data[loc_field]:
                            # Check if it looks like a website/domain (shouldn't be in city)
                            if loc_field == "city" and self._looks_like_website(
                                loc_value
                            ):
                                continue
                            # Truncate location fields to model max_length
                            loc_value = self._truncate_field_value(
                                loc_field, loc_value, Contact
                            )
                            contact_data[loc_field] = loc_value
                elif model_field in ["city", "state", "country"]:
                    # Check if it looks like a website/domain (shouldn't be in city)
                    if self._looks_like_website(value):
                        continue
                    # Check if column name suggests it's a website/domain
                    if any(
                        indicator in csv_col.lower()
                        for indicator in ["domain", "website", "url"]
                    ):
                        continue
                    # Truncate and assign
                    value = self._truncate_field_value(model_field, value, Contact)
                    contact_data[model_field] = value
                elif model_field == "email":
                    # Only set email if it's actually an email, not email_status
                    if "@" in value and value.lower() not in [
                        "verified",
                        "unknown",
                        "unverified",
                    ]:
                        value = self._truncate_field_value(model_field, value, Contact)
                        contact_data[model_field] = value
                elif model_field in ("linkedin", "linkedin_url"):
                    # Contact LinkedIn profile URL: normalize and store
                    value = self.parser.normalize_url(value)
                    if not value or "linkedin.com" not in value.lower():
                        continue
                    value = self._truncate_field_value(model_field, value, Contact)
                    contact_data[model_field] = value
                elif model_field == "birthday":
                    date_obj = self.parser.parse_date(value)
                    if date_obj:
                        contact_data[model_field] = date_obj.date()
                elif model_field == "latest_post":
                    date_obj = self.parser.parse_date(value)
                    if date_obj:
                        contact_data[model_field] = date_obj
                elif model_field == "outreach_status":
                    v = value.strip().lower().replace(" ", "_")
                    valid = {
                        "not_contacted": "not_contacted",
                        "reached_out": "reached_out",
                        "responded": "responded",
                        "bounced": "bounced",
                        "not_a_fit": "not_a_fit",
                    }
                    if v in valid:
                        contact_data[model_field] = valid[v]
                    elif v in ("notcontacted", "not_contacted"):
                        contact_data[model_field] = "not_contacted"
                    elif v in ("reachedout",):
                        contact_data[model_field] = "reached_out"
                elif model_field == "verified":
                    v = (value or "").strip().lower()
                    contact_data[model_field] = v in ("yes", "true", "1", "y")
                else:
                    # Truncate string fields to model max_length
                    value = self._truncate_field_value(model_field, value, Contact)
                    contact_data[model_field] = value

            # Fallback: set contact LinkedIn from row if not already set (handles "linkedin" column
            # and aliases even when mapping missed it, e.g. encoding or column-name quirks)
            if "linkedin" not in contact_data and "linkedin_url" not in contact_data:
                linkedin_aliases = [
                    "linkedin",
                    "linkedin_url",
                    "linkedin_profile",
                    "linkedin_link",
                ]
                for col in row.keys():
                    if not col or not row.get(col):
                        continue
                    col_norm = self.mapper.normalize_column_name(col)
                    if col_norm not in linkedin_aliases:
                        continue
                    val = row[col].strip()
                    if not val or val.lower() in ["false", "true", "null", "none"]:
                        continue
                    if "linkedin.com" not in val.lower():
                        continue
                    val = self.parser.normalize_url(val)
                    if val:
                        val = self._truncate_field_value("linkedin", val, Contact)
                        contact_data["linkedin"] = val
                    break
                # If still empty, use SalesNav Leads (URL) / sales_navigator when it contains a LinkedIn URL
                if "linkedin" not in contact_data:
                    salesnav_aliases = [
                        "sales_navigator",
                        "salesnav_leads_url",  # "SalesNav Leads (URL)"
                        "sales_nav_leads_url",
                        "sales_nav_leads",
                        "salesnav",
                        "sales_nav",
                    ]
                    for col in row.keys():
                        if not col or not row.get(col):
                            continue
                        col_norm = self.mapper.normalize_column_name(col)
                        if col_norm not in salesnav_aliases:
                            continue
                        val = row[col].strip()
                        if not val or val.lower() in ["false", "true", "null", "none"]:
                            continue
                        if "linkedin.com" not in val.lower():
                            continue
                        val = self.parser.normalize_url(val)
                        if val:
                            val = self._truncate_field_value("linkedin", val, Contact)
                            contact_data["linkedin"] = val
                        break

            # Only fill in missing first_name/last_name if full_name wasn't processed
            # This prevents overwriting the correctly parsed full_name with separate columns
            # IMPORTANT: If full_name was processed, NEVER overwrite with separate columns
            if not full_name_processed:
                if "first_name" not in contact_data:
                    for col in ["first_name", "firstname", "fname"]:
                        # Skip company-related columns
                        if "company" in col.lower():
                            continue
                        if col in row and row[col].strip():
                            potential_name = row[col].strip()
                            # Validate it looks like a name and not a company name
                            if self._looks_like_name(
                                potential_name
                            ) and not self._looks_like_company_name(potential_name):
                                first_name_value = self._truncate_field_value(
                                    "first_name", potential_name, Contact
                                )
                                contact_data["first_name"] = first_name_value
                                break

                if "last_name" not in contact_data:
                    # Try to get last_name from separate columns
                    for col in ["last_name", "lastname", "lname", "surname"]:
                        # Skip company-related columns
                        if "company" in col.lower():
                            continue
                        if col in row and row[col].strip():
                            potential_name = row[col].strip()
                            # Validate it looks like a name and not a company name
                            if self._looks_like_name(
                                potential_name
                            ) and not self._looks_like_company_name(potential_name):
                                last_name_value = self._truncate_field_value(
                                    "last_name", potential_name, Contact
                                )
                                contact_data["last_name"] = last_name_value
                                break

            # Link company if available
            if company:
                contact_data["company"] = company

            # Get email - only use actual email addresses, not status values
            email = contact_data.get("email", "").strip()
            if not email:
                # Try to find email in row directly (but skip email_status)
                for col in ["email", "email_address", "e_mail", "mail"]:
                    if col in row and row[col].strip():
                        potential_email = row[col].strip()
                        # Only use if it looks like an email and isn't a status
                        if "@" in potential_email and potential_email.lower() not in [
                            "verified",
                            "unknown",
                            "unverified",
                        ]:
                            email = potential_email
                            email = self._truncate_field_value("email", email, Contact)
                            contact_data["email"] = email
                            break

            # Email is optional - don't require it, but validate if provided
            if email and "@" not in email:
                # Invalid email format, clear it
                email = ""
                contact_data.pop("email", None)

            # Email is now optional - don't raise error if missing
            # But we need a unique identifier for get_or_create, so use email if available, otherwise use a combination
            if not email:
                # Try to create a unique identifier from name + company
                first = contact_data.get("first_name", "")
                last = contact_data.get("last_name", "")
                company_name = contact_data.get("company", "")
                if isinstance(company_name, Company):
                    company_name = company_name.name
                if first and last:
                    # Use a temporary email-like identifier for uniqueness
                    # This will be handled by the create logic below
                    pass

            # Create or update contact
            # If email exists, use it for lookup; otherwise create new
            if email:
                try:
                    contact = Contact.objects.get(email=email)
                    if self.update_existing:
                        for key, value in contact_data.items():
                            if key != "email":  # Don't update email
                                # Truncate string values before setting
                                if isinstance(value, str):
                                    value = self._truncate_field_value(
                                        key, value, Contact
                                    )
                                setattr(contact, key, value)
                        if not contact.owner:
                            contact.owner = self.user
                        contact.save()
                        self.stats["contacts_updated"] += 1
                    else:
                        self.warnings.append(
                            f"Row {row_num}: Contact with email {email} already exists, skipping"
                        )
                except Contact.DoesNotExist:
                    contact = Contact.objects.create(**contact_data, owner=self.user)
                    self.stats["contacts_created"] += 1
            else:
                # No email - if update_existing, try to match by normalized full name (+ company)
                contact = None
                if self.update_existing:
                    first = contact_data.get("first_name", "") or ""
                    last = contact_data.get("last_name", "") or ""
                    name_key = self._normalized_contact_name(first, last)
                    company_id = company.pk if company else None
                    if name_key:
                        lookup = self._get_contact_name_lookup()
                        candidates = lookup.get(name_key, [])
                        # Prefer same company, else take first
                        for cid, c in candidates:
                            if cid == company_id:
                                contact = c
                                break
                        if contact is None and candidates:
                            contact = candidates[0][1]
                if contact is not None:
                    for key, value in contact_data.items():
                        if key == "email":
                            continue
                        if isinstance(value, str):
                            value = self._truncate_field_value(key, value, Contact)
                        setattr(contact, key, value)
                    if not contact.owner:
                        contact.owner = self.user
                    contact.save()
                    self.stats["contacts_updated"] += 1
                else:
                    try:
                        contact = Contact.objects.create(
                            **contact_data, owner=self.user
                        )
                        self.stats["contacts_created"] += 1
                        # So same CSV doesn’t create duplicates: add to name lookup for this run
                        if (
                            self.update_existing
                            and self._contact_name_lookup is not None
                        ):
                            name_key = self._normalized_contact_name(
                                contact.first_name, contact.last_name
                            )
                            if name_key:
                                self._contact_name_lookup[name_key].append(
                                    (contact.company_id, contact)
                                )
                    except Exception as e:
                        self.warnings.append(
                            f"Row {row_num}: Could not create contact without email: {str(e)}"
                        )

            # Pain signal: if company exists and row has pain_signal or pain_signal_url, create PainSignal
            if company and self.import_type in ["contacts", "both"]:
                pain_signal_text = ""
                pain_url = ""
                pain_type_codes = (
                    []
                )  # list of PainType codes from "pain_type" or "pain_signal_type"
                for col in row.keys():
                    if not col:
                        continue
                    col_norm = self.mapper.normalize_column_name(col)
                    val = (row.get(col) or "").strip()
                    if not val:
                        continue
                    if col_norm in ("pain_signal", "pain_signal_text"):
                        pain_signal_text = val[:1000]
                    elif col_norm in ("pain_signal_type", "pain_type"):
                        # Comma-separated codes or single code
                        for code in (
                            c.strip().lower() for c in val.split(",") if c.strip()
                        ):
                            if code in (
                                "job_posting",
                                "glassdoor",
                                "linkedin_activity",
                                "news_press",
                                "association_member",
                                "compliance_issues",
                                "none_found",
                                "other",
                            ):
                                pain_type_codes.append(
                                    code if code != "other" else "none_found"
                                )
                            elif "job" in code or "posting" in code:
                                pain_type_codes.append("job_posting")
                            elif "glassdoor" in code:
                                pain_type_codes.append("glassdoor")
                            elif "linkedin" in code:
                                pain_type_codes.append("linkedin_activity")
                            elif "news" in code or "press" in code:
                                pain_type_codes.append("news_press")
                            elif "association" in code:
                                pain_type_codes.append("association_member")
                            elif "compliance" in code:
                                pain_type_codes.append("compliance_issues")
                            else:
                                pain_type_codes.append("none_found")
                    elif col_norm in ("pain_signal_url", "pain_signal_link"):
                        pain_url = self.parser.normalize_url(val)
                try:
                    contact_for_signal = contact
                except NameError:
                    contact_for_signal = None
                if pain_signal_text or pain_url or pain_type_codes:
                    signal = PainSignal.objects.create(
                        company=company,
                        contact=contact_for_signal,
                        pain_signal=pain_signal_text[:1000],
                        url=pain_url or "",
                        note=pain_signal_text[:1000],
                    )
                    for code in pain_type_codes:
                        try:
                            pt = PainType.objects.get(code=code)
                            signal.pain_types.add(pt)
                        except PainType.DoesNotExist:
                            pass

    def _truncate_field_value(self, field_name: str, value: Any, model_class) -> Any:
        """Truncate field value to model's max_length if it's a CharField."""
        if not isinstance(value, str):
            return value

        try:
            field = model_class._meta.get_field(field_name)
            if hasattr(field, "max_length") and field.max_length:
                if len(value) > field.max_length:
                    self.warnings.append(
                        f"Truncated {field_name} from {len(value)} to {field.max_length} characters"
                    )
                    return value[: field.max_length]
        except Exception:
            # Field doesn't exist or can't get max_length, return as-is
            pass

        return value

    def _looks_like_name(self, value: str) -> bool:
        """Check if a value looks like a person's name (not specialties, location, etc.)."""
        if not value or not value.strip():
            return False

        value_lower = value.lower()

        # Reject if it contains location indicators
        location_indicators = [
            "united states",
            "usa",
            "uk",
            "united kingdom",
            "france",
            "germany",
            "tennessee",
            "new york",
            "connecticut",
            "wisconsin",
            "illinois",
            "south africa",
            "switzerland",
            "india",
            "maharashtra",
            "gauteng",
            "provence",
            "île-de-france",
            "basel",
            "mumbai",
            "johannesburg",
            "paris",
            "marseille",
            "milwaukee",
            "hartford",
            "chattanooga",
            "corning",
            "north chicago",
            "new britain",
            "münchenstein",
        ]
        if any(indicator in value_lower for indicator in location_indicators):
            return False

        # Reject if it's a long comma-separated list (likely specialties/industries)
        if "," in value and len(value.split(",")) > 3:
            return False

        # Reject if it contains common specialty/industry keywords
        specialty_keywords = [
            "biotechnology",
            "innovation",
            "research",
            "development",
            "manufacturing",
            "immunology",
            "neuroscience",
            "oncology",
            "retail",
            "marketing",
            "banking",
            "finance",
            "storage",
            "industrial",
            "tools",
            "rare diseases",
            "blood disorders",
            "diabetes",
            "cardiovascular",
            "vaccines",
            "mutual funds",
            "insurance",
            "logistics",
            "transportation",
            "freight",
            "steel",
            "coils",
            "galvanized",
        ]
        if any(keyword in value_lower for keyword in specialty_keywords):
            return False

        # Reject if it contains URLs or website references
        if "http" in value_lower or "www." in value_lower or ".com" in value_lower:
            return False

        # Reject if it's too long (likely not a name)
        if len(value) > 100:
            return False

        # If it passes all checks, it might be a name
        return True

    def _looks_like_location(self, value: str) -> bool:
        """Check if a value looks like a location (city, state, country format)."""
        if not value or not value.strip():
            return False

        value_lower = value.lower()

        # Check for location indicators
        location_indicators = [
            "united states",
            "usa",
            "uk",
            "united kingdom",
            "france",
            "germany",
            "tennessee",
            "new york",
            "connecticut",
            "wisconsin",
            "illinois",
            "south africa",
            "switzerland",
            "india",
            "maharashtra",
            "gauteng",
            "provence",
            "île-de-france",
            "basel",
            "mumbai",
            "johannesburg",
            "paris",
            "marseille",
            "milwaukee",
            "hartford",
            "chattanooga",
            "corning",
            "north chicago",
            "new britain",
            "münchenstein",
        ]

        # If it contains location indicators, it's likely a location
        if any(indicator in value_lower for indicator in location_indicators):
            return True

        # If it has comma-separated parts that look like city, state, country
        if "," in value:
            parts = [p.strip() for p in value.split(",")]
            # If it has 2-3 parts and contains location indicators, it's likely a location
            if 2 <= len(parts) <= 3:
                combined = " ".join(parts).lower()
                if any(indicator in combined for indicator in location_indicators):
                    return True

        return False

    def _looks_like_company_name(self, value: str) -> bool:
        """Check if a value looks like a company name (not a person's name)."""
        if not value or not value.strip():
            return False

        value_lower = value.lower()

        # Common company name indicators
        company_indicators = [
            "inc",
            "inc.",
            "llc",
            "ltd",
            "ltd.",
            "corp",
            "corp.",
            "corporation",
            "company",
            "co",
            "co.",
            "group",
            "holdings",
            "enterprises",
            "solutions",
            "technologies",
            "tech",
            "systems",
            "services",
            "industries",
            "international",
            "global",
            "worldwide",
            "partners",
            "associates",
            "consulting",
            "capital",
            "ventures",
            "fund",
            "bank",
            "insurance",
            "mutual",
            "electronics",
            "logistics",
        ]

        # Check if it contains company indicators
        if any(indicator in value_lower for indicator in company_indicators):
            return True

        # Check if it's a single word that's commonly a company name
        words = value.split()
        if len(words) == 1 and len(value) > 5:
            # Single long word might be a company name
            if value[0].isupper() and len(value) > 8:
                return True

        # Check if it contains multiple capitalized words (common in company names)
        if len(words) > 1:
            all_caps = all(
                word[0].isupper() if word else False for word in words if word
            )
            if all_caps and len(words) >= 2:
                return True

        return False

    def _looks_like_person_name(self, value: str) -> bool:
        """Check if a value looks like a person's name (not a company name)."""
        if not value or not value.strip():
            return False

        value_lower = value.lower()

        # Common person name indicators
        person_indicators = [
            "dr.",
            "mr.",
            "mrs.",
            "ms.",
            "miss",
            "prof.",
            "professor",
            "jr.",
            "sr.",
            "ii",
            "iii",
            "iv",
            "v",
        ]

        # Check if it starts with a title
        if any(value_lower.startswith(indicator) for indicator in person_indicators):
            return True

        # Check if it contains a comma with a degree (e.g., "Anissa Perkins, MA")
        if "," in value:
            parts = value.split(",")
            if len(parts) == 2:
                second_part = parts[1].strip().upper()
                degree_pattern = r"^(MA|MBA|PhD|MD|JD|LLM|MS|MSc|BS|BA|BSc|EdD|DDS|DVM|RN|LPN|CPA|CFA|PMP|PMI|CCNA|AWS|GCP|Azure)$"
                if re.match(degree_pattern, second_part):
                    return True

        # Check if it's 2-3 words (common for person names, less common for company names)
        words = value.split()
        if 2 <= len(words) <= 3:
            # Check if it doesn't contain company indicators
            if not any(
                indicator in value_lower
                for indicator in [
                    "inc",
                    "llc",
                    "ltd",
                    "corp",
                    "company",
                    "co.",
                    "group",
                    "holdings",
                    "enterprises",
                    "solutions",
                    "technologies",
                    "systems",
                    "services",
                    "industries",
                    "international",
                ]
            ):
                # Might be a person's name
                return True

        return False

    def _looks_like_duration(self, value: str) -> bool:
        """Check if a value looks like a time duration (e.g., '11 years 7 months')."""
        if not value or not value.strip():
            return False

        value_lower = value.lower()

        # Check for duration patterns
        duration_patterns = [
            r"\d+\s*(year|years|yr|yrs)",
            r"\d+\s*(month|months|mo|mos)",
            r"\d+\s*(week|weeks|wk|wks)",
            r"\d+\s*(day|days)",
        ]

        import re

        for pattern in duration_patterns:
            if re.search(pattern, value_lower):
                return True

        # Check for common duration phrases
        duration_phrases = [
            "years",
            "months",
            "weeks",
            "days",
            "time in",
            "duration",
        ]

        if any(phrase in value_lower for phrase in duration_phrases):
            # Additional check: should have numbers
            if re.search(r"\d+", value):
                return True

        return False

    def _looks_like_website(self, value: str) -> bool:
        """Check if a value looks like a website/domain (not a city)."""
        if not value or not value.strip():
            return False

        value_lower = value.lower()

        # Check for URL patterns
        if value_lower.startswith(("http://", "https://", "www.")):
            return True

        # Check for domain patterns (e.g., "example.com", "example.co.uk")
        if re.search(
            r"\.(com|org|net|edu|gov|co|io|ai|uk|us|ca|au|de|fr|it|es|nl|be|ch|at|se|no|dk|fi|pl|cz|hu|ro|gr|pt|ie|nz|za|in|jp|cn|kr|sg|hk|tw|mx|br|ar|cl|co|pe|ae|sa|il|tr|ru|ua|by|kz|ge|am|az)\b",
            value_lower,
        ):
            return True

        # Check for common domain indicators
        domain_indicators = [".com", ".org", ".net", ".co", ".io", ".www"]
        if any(indicator in value_lower for indicator in domain_indicators):
            return True

        return False


def _get_sequence_steps(sequence) -> List[SequenceStep]:
    """Return ordered steps for a sequence."""
    return list(sequence.steps.order_by("order"))


def initialize_sequence_enrollment(
    enrollment: SequenceEnrollment,
    *,
    start_at: Optional[datetime] = None,
) -> None:
    """
    Initialize a sequence enrollment's scheduling fields.

    This sets current_step_index to 0 and computes next_run_at based on the
    first step's offset_days. Call this once when creating a new enrollment.
    """
    steps = _get_sequence_steps(enrollment.sequence)
    if not steps:
        enrollment.status = "completed"
        enrollment.next_run_at = None
        enrollment.save(update_fields=["status", "next_run_at"])
        return

    base = start_at or timezone.now()
    first_step = steps[0]
    enrollment.current_step_index = 0
    enrollment.next_run_at = base + timedelta(days=first_step.offset_days)
    enrollment.status = "active"
    enrollment.save(update_fields=["current_step_index", "next_run_at", "status"])


def _create_activity_for_step(
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    scheduled_for: datetime,
) -> Activity:
    """
    Create an Activity corresponding to a sequence step.

    - For auto_execute email steps, this represents the outbound email.
    - For manual steps (auto_execute=False), this is a task queued for the user.
    """
    contact = enrollment.contact
    company = contact.company if contact and contact.company else None

    # Basic activity scaffolding
    activity = Activity(
        activity_type=step.activity_type,
        direction="outbound" if step.activity_type != "system" else "system",
        subject=step.subject or f"{enrollment.sequence.name} – Step {step.order}",
        description=step.body or "",
        contact=contact,
        company=company,
        deal=enrollment.deal,
        owner=enrollment.owner or contact.owner if contact else None,
        due_date=scheduled_for,
        status="pending" if not step.auto_execute else "sent",
        sequence_step=step,
        sequence_enrollment=enrollment,
    )

    # For manual steps, treat as a task
    if not step.auto_execute or step.activity_type in ["call", "task", "linkedin"]:
        activity.task_type = step.activity_type.upper()
        activity.status = "pending"

    # For email steps we mark as outbound email; actual sending in advance_sequence_enrollment.
    if step.activity_type == "email":
        activity.delivery_status = "queued" if step.auto_execute else ""

    activity.save()
    return activity


def _send_sequence_email(contact, subject: str, body: str, enrollment) -> bool:
    """Send a sequence step email to contact; append unsubscribe link if SITE_URL set. Returns True if sent."""
    if not contact or not getattr(contact, "email", None) or not contact.email:
        return False
    signer = Signer()
    token = quote(signer.sign(str(contact.pk)), safe="")
    site_url = getattr(django_settings, "SITE_URL", "").rstrip("/")
    if site_url:
        unsubscribe_url = f"{site_url}/crm/unsubscribe/?token={token}"
        body = body.rstrip() + f"\n\n---\nUnsubscribe: {unsubscribe_url}"
    from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=[contact.email],
            fail_silently=False,
        )
        return True
    except Exception:
        return False


def advance_sequence_enrollment(
    enrollment: SequenceEnrollment,
    *,
    now: Optional[datetime] = None,
) -> Optional[Activity]:
    """
    Advance a sequence enrollment by executing its next step if due.

    This is a pure engine-style helper:
    - It respects enrollment.status ('active' only).
    - It checks contact consent before executing email/call/linkedin steps.
    - It creates an Activity for the current step.
    - It updates current_step_index, last_executed_step, next_run_at, and status.

    Returns the Activity that was created for this step, or None if nothing ran.
    """
    if enrollment.status != "active":
        return None

    steps = _get_sequence_steps(enrollment.sequence)
    if not steps:
        enrollment.status = "completed"
        enrollment.next_run_at = None
        enrollment.save(update_fields=["status", "next_run_at"])
        return None

    now = now or timezone.now()
    if enrollment.next_run_at and enrollment.next_run_at > now:
        # Not yet time to run next step
        return None

    if enrollment.current_step_index >= len(steps):
        enrollment.status = "completed"
        enrollment.next_run_at = None
        enrollment.save(update_fields=["status", "next_run_at"])
        return None

    step = steps[enrollment.current_step_index]
    contact = enrollment.contact

    # Consent checks per channel before executing anything automated.
    if step.activity_type == "email" and contact and not contact.can_email_outbound:
        enrollment.status = "paused"
        enrollment.next_run_at = None
        enrollment.save(update_fields=["status", "next_run_at"])
        Activity.objects.create(
            activity_type="system",
            direction="system",
            subject="Sequence halted: email consent revoked",
            description=(
                f"Sequence '{enrollment.sequence.name}' paused because "
                "outbound email is not permitted for this contact."
            ),
            contact=contact,
            company=contact.company if contact.company else None,
            sequence_enrollment=enrollment,
            status="completed",
        )
        return None

    if step.activity_type == "call" and contact and not contact.can_call:
        enrollment.status = "paused"
        enrollment.next_run_at = None
        enrollment.save(update_fields=["status", "next_run_at"])
        return None

    if (
        step.activity_type in ["linkedin", "task"]
        and contact
        and not contact.can_linkedin
    ):
        enrollment.status = "paused"
        enrollment.next_run_at = None
        enrollment.save(update_fields=["status", "next_run_at"])
        return None

    # Execute current step
    activity = _create_activity_for_step(enrollment, step, now)

    # Send email for auto-execute email steps
    if (
        step.activity_type == "email"
        and step.auto_execute
        and contact
        and getattr(contact, "email", None)
        and contact.email
    ):
        sent = _send_sequence_email(
            contact,
            activity.subject,
            activity.description or "",
            enrollment,
        )
        if sent:
            activity.status = "sent"
            activity.delivery_status = "sent"
            activity.completed_date = now
            activity.save(update_fields=["status", "delivery_status", "completed_date"])

    # Advance pointer
    enrollment.current_step_index += 1
    enrollment.last_executed_step = step

    if enrollment.current_step_index >= len(steps):
        enrollment.status = "completed"
        enrollment.next_run_at = None
    else:
        next_step = steps[enrollment.current_step_index]
        enrollment.next_run_at = now + timedelta(days=next_step.offset_days)

    enrollment.save(
        update_fields=[
            "current_step_index",
            "last_executed_step",
            "next_run_at",
            "status",
        ]
    )
    return activity


def calculate_icp_fit_for_company(company: Company) -> Tuple[int, str]:
    """
    Calculate a simple ICP fit score and tier for a company.

    This follows a HubSpot-style manual scoring approach using:
    - Industry (match to target industries)
    - Employee count (ideal size band)
    - Country/region
    - Basic completeness/credibility signals (website/LinkedIn, revenue)

    You can tune the constants below to reflect your real ICP.
    """
    score = 0

    # --- Configuration (tune these to your ICP) ---
    TARGET_INDUSTRIES = {
        "software",
        "computer software",
        "information technology and services",
        "internet",
        "saas",
    }
    TARGET_COUNTRIES = {
        "united states",
        "usa",
        "canada",
        "united kingdom",
        "uk",
        "ireland",
        "australia",
        "new zealand",
    }
    IDEAL_EMPLOYEE_MIN = 10
    IDEAL_EMPLOYEE_MAX = 500

    # --- Industry fit ---
    if company.industry:
        industry_normalized = company.industry.strip().lower()
        if industry_normalized in TARGET_INDUSTRIES:
            score += 30

    # --- Company size fit ---
    if company.employee_count is not None:
        if IDEAL_EMPLOYEE_MIN <= company.employee_count <= IDEAL_EMPLOYEE_MAX:
            score += 30
        elif company.employee_count < IDEAL_EMPLOYEE_MIN:
            score += 5  # small but potentially interesting
        else:
            # Very large orgs often require different motion
            score += 10

    # --- Geography fit ---
    if company.country:
        if company.country.strip().lower() in TARGET_COUNTRIES:
            score += 20

    # --- Signal: digital presence ---
    if company.website:
        score += 5
    if company.linkedin_url:
        score += 5

    # --- Signal: revenue available ---
    if company.annual_revenue:
        score += 5

    # Clamp to 0–100
    score = max(0, min(score, 100))

    # Map to a simple tier
    if score >= 80:
        tier = "A"
    elif score >= 60:
        tier = "B"
    elif score >= 40:
        tier = "C"
    else:
        tier = "D"

    return score, tier


def _normalized_contact_name(contact):
    first = (contact.first_name or "").strip()
    last = (contact.last_name or "").strip()
    return " ".join((first + " " + last).split()).lower()


def find_contact_duplicate_groups(queryset=None):
    """Group contacts by normalized full name or email; return list of (key, list of contacts)."""
    from collections import defaultdict

    qs = queryset or Contact.objects.filter(is_active=True)
    qs = qs.select_related("company").order_by("id")
    by_name = defaultdict(list)
    by_email = defaultdict(list)
    for c in qs:
        name_key = _normalized_contact_name(c)
        if name_key:
            by_name[name_key].append(c)
        email_key = (c.email or "").strip().lower()
        if email_key:
            by_email[email_key].append(c)
    groups = []
    seen_ids = set()
    for key, candidates in by_name.items():
        if len(candidates) > 1:
            group = [c for c in candidates if c.id not in seen_ids]
            if len(group) > 1:
                groups.append(("name", key, group))
                seen_ids.update(c.id for c in group)
    for key, candidates in by_email.items():
        if len(candidates) > 1:
            group = [c for c in candidates if c.id not in seen_ids]
            if len(group) > 1:
                groups.append(("email", key, group))
                seen_ids.update(c.id for c in group)
    return groups


def merge_contacts(canonical, duplicates):
    """Merge duplicate contacts into canonical: move related objects, copy missing fields, soft-delete duplicates."""
    from django.db import transaction

    with transaction.atomic():
        for dup in duplicates:
            if dup.id == canonical.id:
                continue
            for attr in (
                "email",
                "phone",
                "mobile",
                "job_title",
                "company",
                "notes",
                "linkedin",
            ):
                if not getattr(canonical, attr, None) and getattr(dup, attr, None):
                    setattr(canonical, attr, getattr(dup, attr))
            Activity.objects.filter(contact=dup).update(contact=canonical)
            Deal.objects.filter(contact=dup).update(contact=canonical)
            SequenceEnrollment.objects.filter(contact=dup).update(contact=canonical)
            PainSignal.objects.filter(contact=dup).update(contact=canonical)
            dup.is_active = False
            dup.save(update_fields=["is_active"])
        canonical.save()
    return canonical


def find_company_duplicate_groups(queryset=None):
    """Group companies by normalized name or domain; return list of (key_type, key, list of companies)."""
    from collections import defaultdict
    from urllib.parse import urlparse

    qs = queryset or Company.objects.filter(is_active=True)
    qs = qs.order_by("id")
    by_name = defaultdict(list)
    by_domain = defaultdict(list)
    for c in qs:
        name_key = (c.name or "").strip().lower()
        if name_key:
            by_name[name_key].append(c)
        if c.website:
            try:
                domain = urlparse(c.website).netloc or urlparse(c.website).path
                domain = (domain or "").strip().lower().replace("www.", "")
                if domain:
                    by_domain[domain].append(c)
            except Exception:
                pass
    groups = []
    seen_ids = set()
    for key, candidates in by_name.items():
        if len(candidates) > 1:
            group = [c for c in candidates if c.id not in seen_ids]
            if len(group) > 1:
                groups.append(("name", key, group))
                seen_ids.update(c.id for c in group)
    for key, candidates in by_domain.items():
        if len(candidates) > 1:
            group = [c for c in candidates if c.id not in seen_ids]
            if len(group) > 1:
                groups.append(("domain", key, group))
                seen_ids.update(c.id for c in group)
    return groups


def merge_companies(canonical, duplicates):
    """Merge duplicate companies into canonical: move related objects, copy missing fields, soft-delete duplicates."""
    from django.db import transaction

    with transaction.atomic():
        for dup in duplicates:
            if dup.id == canonical.id:
                continue
            for attr in (
                "website",
                "phone",
                "email",
                "industry",
                "description",
                "address",
                "city",
                "country",
            ):
                if not getattr(canonical, attr, None) and getattr(dup, attr, None):
                    setattr(canonical, attr, getattr(dup, attr))
            Contact.objects.filter(company=dup).update(company=canonical)
            Deal.objects.filter(company=dup).update(company=canonical)
            Activity.objects.filter(company=dup).update(company=canonical)
            PainSignal.objects.filter(company=dup).update(company=canonical)
            dup.is_active = False
            dup.save(update_fields=["is_active"])
        canonical.save()
    return canonical
