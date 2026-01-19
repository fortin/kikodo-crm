import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import CustomMetric, DashboardTemplate


class CSVImportError(Exception):
    """Custom exception for CSV import errors"""

    pass


class CSVImporter:
    """Handles CSV import for dashboard templates"""

    def __init__(self, template_id, user_id):
        self.template = DashboardTemplate.objects.get(id=template_id)
        self.user = User.objects.get(id=user_id)
        self.errors = []
        self.warnings = []

    def parse_csv(self, csv_file):
        """Parse CSV file and extract metrics data"""
        try:
            # Read CSV content
            content = csv_file.read().decode("utf-8")
            csv_reader = csv.DictReader(io.StringIO(content))

            # Validate headers
            headers = csv_reader.fieldnames
            if not headers:
                raise CSVImportError("CSV file is empty or has no headers")

            # Extract metric names from headers
            metric_names = self._extract_metric_names(headers)

            # Parse data rows
            metrics_data = []
            for row_num, row in enumerate(
                csv_reader, start=2
            ):  # Start at 2 because of header
                try:
                    period_data = self._parse_row(row, metric_names, row_num)
                    if period_data:
                        metrics_data.append(period_data)
                except Exception as e:
                    self.errors.append(f"Row {row_num}: {str(e)}")

            return metrics_data

        except Exception as e:
            raise CSVImportError(f"Failed to parse CSV: {str(e)}")

    def _extract_metric_names(self, headers):
        """Extract metric names from CSV headers"""
        metric_names = []

        for header in headers:
            if header and header.strip():
                # Skip empty columns and period columns
                if header.lower() in ["", "period", "week", "month", "quarter", "year"]:
                    continue
                
                # Skip percentage achieved columns (we'll calculate these)
                if " (% Achieved)" in header:
                    continue

                # Extract metric name (remove target/actual suffixes)
                metric_name = header.strip()
                if " (Target)" in metric_name:
                    metric_name = metric_name.replace(" (Target)", "")
                elif " (Actual)" in metric_name:
                    metric_name = metric_name.replace(" (Actual)", "")

                if metric_name and metric_name not in metric_names:
                    metric_names.append(metric_name)

        return metric_names

    def _parse_row(self, row, metric_names, row_num):
        """Parse a single row of CSV data"""
        period_data = {"period": None, "metrics": {}}

        # Extract period information - check first column (often unnamed) or look for period-like columns
        period_found = False
        
        # First, try the first column (often unnamed but contains period info)
        first_key = list(row.keys())[0] if row.keys() else None
        if first_key and row[first_key] and row[first_key].strip():
            period_value = row[first_key].strip()
            # Check if it looks like a period (contains "Week", "Month", etc.)
            if any(word in period_value.lower() for word in ["week", "month", "quarter", "year", "q1", "q2", "q3", "q4"]):
                period_data["period"] = period_value
                period_found = True
        
        # If not found in first column, look for explicitly named period columns
        if not period_found:
            for key, value in row.items():
                if (
                    key
                    and value
                    and key.lower() in ["period", "week", "month", "quarter", "year"]
                ):
                    period_data["period"] = value.strip()
                    period_found = True
                    break

        if not period_found:
            raise ValidationError("No period information found in row")

        # Extract metric values
        for metric_name in metric_names:
            target_key = f"{metric_name} (Target)"
            actual_key = f"{metric_name} (Actual)"

            target_value = None
            actual_value = None

            # Get target value
            if target_key in row and row[target_key]:
                try:
                    target_value = self._parse_number(row[target_key])
                except ValueError:
                    self.warnings.append(
                        f"Row {row_num}: Invalid target value for {metric_name}"
                    )

            # Get actual value
            if actual_key in row and row[actual_key]:
                try:
                    actual_value = self._parse_number(row[actual_key])
                except ValueError:
                    self.warnings.append(
                        f"Row {row_num}: Invalid actual value for {metric_name}"
                    )

            if target_value is not None or actual_value is not None:
                period_data["metrics"][metric_name] = {
                    "target_value": target_value,
                    "actual_value": actual_value,
                    "metric_type": self._guess_metric_type(metric_name),
                    "unit": self._guess_unit(metric_name),
                }

        return period_data

    def _parse_number(self, value):
        """Parse a string value to a number"""
        if not value or value.strip() == "":
            return None

        value = value.strip()

        # Handle percentage values
        if value.endswith("%"):
            value = value[:-1]

        # Handle comma separators
        if "," in value:
            value = value.replace(",", "")

        try:
            return Decimal(value)
        except InvalidOperation:
            raise ValueError(f"Invalid number format: {value}")

    def _guess_metric_type(self, metric_name):
        """Guess the metric type based on the name"""
        metric_name_lower = metric_name.lower()

        if any(
            word in metric_name_lower for word in ["percentage", "%", "rate", "ratio"]
        ):
            return "percentage"
        elif any(
            word in metric_name_lower
            for word in ["revenue", "sales", "amount", "value", "cost", "price"]
        ):
            return "currency"
        elif any(word in metric_name_lower for word in ["average", "avg", "mean"]):
            return "average"
        else:
            return "count"

    def _guess_unit(self, metric_name):
        """Guess the unit based on the metric name"""
        metric_name_lower = metric_name.lower()

        if "posts" in metric_name_lower:
            return "posts"
        elif "connections" in metric_name_lower:
            return "connections"
        elif "comments" in metric_name_lower or "likes" in metric_name_lower:
            return "interactions"
        elif "conversations" in metric_name_lower or "dms" in metric_name_lower:
            return "conversations"
        elif "meetings" in metric_name_lower:
            return "meetings"
        elif "webinars" in metric_name_lower:
            return "webinars"
        elif "pilots" in metric_name_lower:
            return "pilots"
        elif "case studies" in metric_name_lower:
            return "case studies"
        else:
            return ""

    def import_metrics(self, csv_file):
        """Import metrics from CSV file"""
        try:
            # Parse CSV data
            metrics_data = self.parse_csv(csv_file)

            # Create or update metrics
            created_count = 0
            updated_count = 0

            for period_data in metrics_data:
                period = period_data["period"]

                for metric_name, metric_data in period_data["metrics"].items():
                    metric, created = CustomMetric.objects.get_or_create(
                        template=self.template,
                        metric_name=metric_name,
                        period=period,
                        defaults={
                            "description": f"Imported metric: {metric_name}",
                            "target_value": metric_data["target_value"],
                            "actual_value": metric_data["actual_value"],
                            "metric_type": metric_data["metric_type"],
                            "unit": metric_data["unit"],
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        # Update existing metric
                        metric.target_value = metric_data["target_value"]
                        metric.actual_value = metric_data["actual_value"]
                        metric.metric_type = metric_data["metric_type"]
                        metric.unit = metric_data["unit"]
                        metric.save()
                        updated_count += 1

            return {
                "success": True,
                "created_count": created_count,
                "updated_count": updated_count,
                "errors": self.errors,
                "warnings": self.warnings,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "errors": self.errors,
                "warnings": self.warnings,
            }


def create_sample_template(user):
    """Create a sample dashboard template"""
    template = DashboardTemplate.objects.create(
        name="Sample Marketing Metrics",
        description="Sample template for marketing metrics tracking",
        created_by=user,
        period_type="weekly",
        is_active=True,
        is_public=True,
    )

    # Create sample metrics
    sample_metrics = [
        {
            "metric_name": "Posts published",
            "description": "Number of social media posts published",
            "metric_type": "count",
            "unit": "posts",
        },
        {
            "metric_name": "Total ICP connections",
            "description": "Number of ideal customer profile connections",
            "metric_type": "count",
            "unit": "connections",
        },
        {
            "metric_name": "Inbound comments/likes",
            "description": "Number of inbound social media interactions",
            "metric_type": "count",
            "unit": "interactions",
        },
        {
            "metric_name": "Warm DM conversations",
            "description": "Number of warm direct message conversations",
            "metric_type": "count",
            "unit": "conversations",
        },
        {
            "metric_name": "Meetings booked",
            "description": "Number of meetings booked",
            "metric_type": "count",
            "unit": "meetings",
        },
        {
            "metric_name": "Webinars hosted",
            "description": "Number of webinars hosted",
            "metric_type": "count",
            "unit": "webinars",
        },
        {
            "metric_name": "Pilots launched",
            "description": "Number of pilot programs launched",
            "metric_type": "count",
            "unit": "pilots",
        },
        {
            "metric_name": "Case studies published",
            "description": "Number of case studies published",
            "metric_type": "count",
            "unit": "case studies",
        },
    ]

    for i, metric_data in enumerate(sample_metrics):
        for week in range(1, 13):  # 12 weeks
            CustomMetric.objects.create(
                template=template,
                metric_name=metric_data["metric_name"],
                description=metric_data["description"],
                period=f"Week {week}",
                target_value=Decimal(str(week * 3)),  # Sample target values
                actual_value=None,  # Will be filled by user
                metric_type=metric_data["metric_type"],
                unit=metric_data["unit"],
            )

    return template
