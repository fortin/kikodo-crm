# Kikodo CRM

A comprehensive Customer Relationship Management (CRM) system built with Django, featuring operational and analytical capabilities inspired by HubSpot and Airtable. The system provides a modern, clean interface with powerful data management and analytics features.

## Features

### Core CRM Functionality
- **Contact Management**: Complete contact profiles with professional information, communication history, and relationship tracking
- **Company Management**: Organization profiles with industry classification, revenue tracking, and employee counts
- **Deal Pipeline**: Sales opportunity tracking with stages, probabilities, and revenue forecasting
- **Activity Tracking**: Comprehensive activity logging including calls, emails, meetings, tasks, and notes
- **Tag System**: Flexible categorization and organization of contacts, companies, and deals

### Analytics & Reporting
- **Dashboard**: Real-time metrics and visualizations with Airtable-inspired design
- **Pipeline Analytics**: Sales funnel analysis with stage-by-stage breakdown
- **Activity Analytics**: Performance tracking and engagement metrics
- **Custom Reports**: Flexible reporting system with filtering and export capabilities
- **Sales Goals**: Target setting and progress tracking

### Modern UI/UX
- **Airtable-inspired Design**: Clean, modern interface with intuitive data visualization
- **Responsive Layout**: Mobile-friendly design that works across all devices
- **Interactive Charts**: Real-time data visualization using Chart.js
- **Data Grids**: Airtable-style data presentation with hover effects and clean typography
- **Color-coded Status**: Visual status indicators and badges for quick information scanning

## Technology Stack

- **Backend**: Django 4.2.7 with Django REST Framework
- **Database**: SQLite (development) / PostgreSQL (production)
- **Frontend**: Bootstrap 5, Chart.js, Font Awesome
- **Authentication**: Django's built-in authentication system
- **API**: RESTful API with comprehensive endpoints
- **Styling**: Custom CSS with Airtable-inspired design system

## Documentation

### For Users
- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 5 minutes
- **[User Documentation](docs/USER_DOCUMENTATION.md)** - Comprehensive user guide covering all features

### For Developers
- **[API Documentation](docs/API_DOCUMENTATION.md)** - Complete REST API reference with examples
- **[Installation Guide](#installation)** - Detailed setup instructions
- **[Configuration](#configuration)** - Environment and database setup

### Documentation Features
- **Step-by-step guides** for all major features
- **Screenshots and examples** for better understanding
- **API examples** in multiple programming languages
- **Troubleshooting guides** for common issues
- **Best practices** for optimal usage

## Installation

### Prerequisites
- Python 3.8+
- pip (Python package installer)
- Git
- PostgreSQL (for production)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd kikodo-crm
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Populate with sample data (optional)**
   ```bash
   python manage.py populate_data
   ```

7. **Start the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Main application: http://localhost:8000/
   - Admin interface: http://localhost:8000/admin/
   - API endpoints: http://localhost:8000/crm/api/

## Default Login Credentials

After running the populate_data command:
- **Username**: admin
- **Password**: admin123

## API Endpoints

The system provides comprehensive REST API endpoints:

### Contacts
- `GET /crm/api/contacts/` - List all contacts
- `POST /crm/api/contacts/` - Create new contact
- `GET /crm/api/contacts/{id}/` - Get contact details
- `PUT /crm/api/contacts/{id}/` - Update contact
- `DELETE /crm/api/contacts/{id}/` - Delete contact
- `GET /crm/api/contacts/stats/` - Get contact statistics

### Companies
- `GET /crm/api/companies/` - List all companies
- `POST /crm/api/companies/` - Create new company
- `GET /crm/api/companies/{id}/` - Get company details
- `PUT /crm/api/companies/{id}/` - Update company
- `DELETE /crm/api/companies/{id}/` - Delete company
- `GET /crm/api/companies/stats/` - Get company statistics

### Deals
- `GET /crm/api/deals/` - List all deals
- `POST /crm/api/deals/` - Create new deal
- `GET /crm/api/deals/{id}/` - Get deal details
- `PUT /crm/api/deals/{id}/` - Update deal
- `DELETE /crm/api/deals/{id}/` - Delete deal
- `GET /crm/api/deals/pipeline/` - Get pipeline data
- `GET /crm/api/deals/stats/` - Get deal statistics

### Activities
- `GET /crm/api/activities/` - List all activities
- `POST /crm/api/activities/` - Create new activity
- `GET /crm/api/activities/{id}/` - Get activity details
- `PUT /crm/api/activities/{id}/` - Update activity
- `DELETE /crm/api/activities/{id}/` - Delete activity
- `GET /crm/api/activities/upcoming/` - Get upcoming activities
- `GET /crm/api/activities/stats/` - Get activity statistics

## Data Models

### Core Models
- **Contact**: Individual person records with contact information and CRM status
- **Company**: Organization records with business information and metrics
- **Deal**: Sales opportunities with pipeline stages and revenue tracking
- **Activity**: Interaction records including calls, emails, meetings, and tasks
- **Tag**: Flexible categorization system for all entities

### Analytics Models
- **DashboardWidget**: Customizable dashboard components
- **Report**: Saved report configurations
- **SalesGoal**: Target setting and tracking
- **ActivitySummary**: Daily activity aggregations
- **CustomField**: Extensible field system for additional data

## Configuration

### Environment Variables
Create a `.env` file in the project root with the following variables:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://user:password@localhost:5432/kikodo_crm
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Database Configuration
The system uses SQLite by default for development. For production, configure PostgreSQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'kikodo_crm',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Deployment

### Production Setup
1. Set `DEBUG=False` in settings
2. Configure a production database (PostgreSQL recommended)
3. Set up static file serving with WhiteNoise or a CDN
4. Configure email settings for notifications
5. Set up Redis for caching and background tasks
6. Use Gunicorn as the WSGI server

### Docker Deployment
```bash
# Build the image
docker build -t kikodo-crm .

# Run the container
docker run -p 8000:8000 kikodo-crm
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions, please open an issue in the GitHub repository or contact the development team.

## Roadmap

### Planned Features
- **Strategic CRM**: Advanced customer segmentation and lifecycle management
- **Collaborative CRM**: Team collaboration features and shared workspaces
- **Mobile App**: Native mobile application for iOS and Android
- **Advanced Analytics**: Machine learning insights and predictive analytics
- **Integration Hub**: Third-party integrations with popular business tools
- **Workflow Automation**: Automated task creation and follow-up sequences
- **Document Management**: File storage and document sharing capabilities
- **Email Integration**: Direct email integration and tracking
- **Calendar Sync**: Calendar integration for meeting scheduling
- **Advanced Reporting**: Custom report builder with drag-and-drop interface
