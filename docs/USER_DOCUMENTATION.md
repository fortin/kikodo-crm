# Kikodo CRM - User Documentation

## Table of Contents
1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Managing Contacts](#managing-contacts)
4. [Managing Companies](#managing-companies)
5. [Managing Deals](#managing-deals)
6. [Managing Activities](#managing-activities)
7. [Analytics & Reports](#analytics--reports)
8. [Admin Interface](#admin-interface)
9. [API Usage](#api-usage)
10. [Troubleshooting](#troubleshooting)
11. [Keyboard Shortcuts](#keyboard-shortcuts)
12. [Best Practices](#best-practices)

---

## Getting Started

### First Login
1. Navigate to `http://localhost:8000/`
2. Click "Login" or go directly to `http://localhost:8000/admin/`
3. Use the default credentials:
   - **Username**: `admin`
   - **Password**: `admin123`
4. Change your password immediately after first login

### Navigation Overview
The Kikodo CRM interface features a clean, Airtable-inspired design with:
- **Sidebar Navigation**: Quick access to all main sections
- **Dashboard**: Overview of key metrics and recent activity
- **Data Grids**: Airtable-style data presentation
- **Modern UI**: Clean, professional interface

---

## Dashboard Overview

The dashboard provides a comprehensive overview of your CRM data:

### Key Metrics
- **Total Contacts**: Number of active contacts in your database
- **Total Companies**: Number of active companies
- **Total Deals**: Number of active deals in your pipeline
- **Total Activities**: Number of activities tracked

### Pipeline Visualization
- Visual representation of deals by stage
- Revenue amounts for each pipeline stage
- Quick overview of sales performance

### Recent Activity Feed
- Latest activities across all contacts and companies
- Upcoming activities requiring attention
- Recent deals and their status

### Monthly Trends Chart
- 6-month view of contacts, deals, and revenue
- Visual trend analysis
- Performance tracking over time

---

## Managing Contacts

### Viewing Contacts
1. Click **"Contacts"** in the sidebar
2. View all contacts in the Airtable-style data grid
3. Each contact shows:
   - Full name
   - Company affiliation
   - Job title
   - Status badge
   - Email address

### Contact Information
Each contact includes:
- **Personal Details**: First name, last name, email, phone
- **Professional Info**: Job title, department
- **Company Association**: Linked company record
- **Status**: Active, Inactive, Lead, Customer
- **Tags**: Custom labels for categorization
- **Activities**: Related activities and interactions

### Contact Status Types
- **Active**: Currently engaged contact
- **Inactive**: No recent activity
- **Lead**: Potential customer
- **Customer**: Confirmed customer

---

## Managing Companies

### Viewing Companies
1. Click **"Companies"** in the sidebar
2. Browse companies in the data grid format
3. Each company displays:
   - Company name
   - Industry
   - Location (city, state)
   - Annual revenue
   - Employee count

### Company Information
Companies include:
- **Basic Details**: Name, website, description
- **Industry Classification**: Business sector
- **Location**: Address, city, state, country
- **Financial Info**: Annual revenue, employee count
- **Status**: Active/Inactive
- **Tags**: Custom categorization
- **Associated Contacts**: People from this company

### Company Status Management
- **Active**: Currently doing business
- **Inactive**: No current relationship
- **Prospect**: Potential customer
- **Customer**: Confirmed business relationship

---

## Managing Deals

### Viewing Deals
1. Click **"Deals"** in the sidebar
2. View all deals in the pipeline
3. Each deal shows:
   - Deal name
   - Associated contact and company
   - Deal amount
   - Pipeline stage
   - Expected close date

### Deal Pipeline Stages
- **Lead**: Initial interest
- **Qualified**: Verified potential
- **Proposal**: Formal proposal sent
- **Negotiation**: Terms being discussed
- **Closed Won**: Deal completed successfully
- **Closed Lost**: Deal did not close

### Deal Information
Each deal includes:
- **Basic Details**: Name, description, amount
- **Timeline**: Expected close date, actual close date
- **Associated Records**: Contact, company, activities
- **Pipeline Stage**: Current position in sales process
- **Probability**: Likelihood of closing
- **Tags**: Custom labels

---

## Managing Activities

### Viewing Activities
1. Click **"Activities"** in the sidebar
2. View all activities in chronological order
3. Each activity shows:
   - Activity type badge
   - Subject/description
   - Associated contact or company
   - Status
   - Due date

### Activity Types
- **Call**: Phone conversations
- **Email**: Email communications
- **Meeting**: In-person or virtual meetings
- **Task**: General tasks and to-dos
- **Note**: General notes and observations

### Activity Status
- **Pending**: Not yet started
- **In Progress**: Currently being worked on
- **Completed**: Finished
- **Cancelled**: No longer needed

### Activity Management
- **Due Dates**: Set deadlines for activities
- **Priority Levels**: High, Medium, Low
- **Associated Records**: Link to contacts, companies, deals
- **Notes**: Detailed descriptions and outcomes

---

## Analytics & Reports

### Analytics Dashboard
1. Click **"Analytics"** in the sidebar
2. View comprehensive analytics (coming soon)
3. Features will include:
   - Advanced sales analytics
   - Performance metrics
   - Custom reports
   - Data visualization

### Reports Section
1. Click **"Reports"** in the sidebar
2. Access reporting features (coming soon)
3. Planned features:
   - Custom report builder
   - Export to PDF/Excel
   - Scheduled reports
   - Advanced filtering

---

## Admin Interface

### Accessing Admin
1. Click **"Admin"** in the sidebar
2. Or navigate to `http://localhost:8000/admin/`
3. Use your admin credentials

### Admin Features
- **User Management**: Create and manage user accounts
- **Data Management**: Direct database access
- **System Configuration**: Settings and preferences
- **Bulk Operations**: Mass data updates
- **Advanced Filtering**: Complex data queries

### User Roles
- **Admin**: Full system access
- **Manager**: Limited admin access
- **User**: Standard CRM access
- **Viewer**: Read-only access

---

## API Usage

### REST API Endpoints
The CRM provides a comprehensive REST API:

#### Contacts API
- `GET /crm/api/contacts/` - List all contacts
- `POST /crm/api/contacts/` - Create new contact
- `GET /crm/api/contacts/{id}/` - Get specific contact
- `PUT /crm/api/contacts/{id}/` - Update contact
- `DELETE /crm/api/contacts/{id}/` - Delete contact

#### Companies API
- `GET /crm/api/companies/` - List all companies
- `POST /crm/api/companies/` - Create new company
- `GET /crm/api/companies/{id}/` - Get specific company
- `PUT /crm/api/companies/{id}/` - Update company
- `DELETE /crm/api/companies/{id}/` - Delete company

#### Deals API
- `GET /crm/api/deals/` - List all deals
- `POST /crm/api/deals/` - Create new deal
- `GET /crm/api/deals/{id}/` - Get specific deal
- `PUT /crm/api/deals/{id}/` - Update deal
- `DELETE /crm/api/deals/{id}/` - Delete deal

#### Activities API
- `GET /crm/api/activities/` - List all activities
- `POST /crm/api/activities/` - Create new activity
- `GET /crm/api/activities/{id}/` - Get specific activity
- `PUT /crm/api/activities/{id}/` - Update activity
- `DELETE /crm/api/activities/{id}/` - Delete activity

### API Authentication
- Use Django's built-in authentication
- Include authentication headers in requests
- API supports both session and token authentication

### API Filtering
- Use query parameters for filtering
- Example: `/crm/api/contacts/?status=active`
- Supports multiple filter combinations

---

## Troubleshooting

### Common Issues

#### Login Problems
- **Forgot Password**: Use admin interface to reset
- **Account Locked**: Contact system administrator
- **Session Expired**: Refresh page and login again

#### Data Not Loading
- **Check Internet Connection**: Ensure stable connection
- **Clear Browser Cache**: Refresh with Ctrl+F5
- **Check Database**: Verify PostgreSQL is running

#### Template Errors
- **Page Not Loading**: Check for template syntax errors
- **Missing Data**: Verify database migrations are applied
- **Styling Issues**: Clear browser cache

### Performance Issues
- **Slow Loading**: Check database performance
- **Memory Usage**: Monitor server resources
- **Large Datasets**: Use pagination and filtering

### Browser Compatibility
- **Chrome**: Recommended browser
- **Firefox**: Fully supported
- **Safari**: Supported
- **Edge**: Supported

---

## Keyboard Shortcuts

### Navigation
- **Ctrl + 1**: Dashboard
- **Ctrl + 2**: Contacts
- **Ctrl + 3**: Companies
- **Ctrl + 4**: Deals
- **Ctrl + 5**: Activities
- **Ctrl + 6**: Analytics
- **Ctrl + 7**: Reports

### General
- **Ctrl + S**: Save (where applicable)
- **Ctrl + F**: Search/Find
- **Ctrl + N**: New record (where applicable)
- **Esc**: Close modal/cancel action

---

## Best Practices

### Data Management
1. **Consistent Naming**: Use standard formats for names and titles
2. **Regular Updates**: Keep contact and company information current
3. **Tag Usage**: Use tags consistently for better organization
4. **Data Validation**: Ensure email addresses and phone numbers are valid

### Contact Management
1. **Complete Profiles**: Fill in all available contact information
2. **Regular Follow-ups**: Schedule activities for ongoing relationships
3. **Status Updates**: Keep contact status current
4. **Company Associations**: Link contacts to their companies

### Deal Management
1. **Realistic Amounts**: Use accurate deal values
2. **Timeline Accuracy**: Set realistic close dates
3. **Stage Progression**: Move deals through pipeline stages
4. **Activity Tracking**: Log all deal-related activities

### Activity Management
1. **Timely Logging**: Record activities promptly
2. **Detailed Notes**: Include comprehensive descriptions
3. **Follow-up Scheduling**: Set reminders for important activities
4. **Outcome Recording**: Document results and next steps

### System Maintenance
1. **Regular Backups**: Ensure data is backed up regularly
2. **User Training**: Train team members on proper usage
3. **Data Cleanup**: Periodically review and clean up old data
4. **Performance Monitoring**: Monitor system performance

---

## Support and Resources

### Getting Help
- **Documentation**: Refer to this user guide
- **Admin Interface**: Use admin tools for advanced operations
- **API Documentation**: Use REST API for integrations
- **System Logs**: Check logs for error details

### Training Resources
- **Dashboard Tour**: Explore all dashboard features
- **Sample Data**: Use provided sample data for practice
- **Admin Training**: Learn admin interface capabilities
- **API Examples**: Study API usage examples

### System Requirements
- **Browser**: Modern web browser (Chrome recommended)
- **Internet**: Stable internet connection
- **Database**: PostgreSQL 12+ (for production)
- **Server**: Django-compatible hosting

---

*This documentation is regularly updated. For the latest version, check the project repository.*
