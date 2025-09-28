from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    Company, Contact, Deal, Activity, Tag, 
    ContactTag, CompanyTag, DealTag, Pipeline, PipelineStage
)
from .serializers import (
    CompanySerializer, ContactSerializer, DealSerializer, ActivitySerializer,
    TagSerializer, PipelineSerializer, PipelineStageSerializer,
    ContactTagSerializer, CompanyTagSerializer, DealTagSerializer
)


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['industry', 'is_active', 'owner']
    search_fields = ['name', 'email', 'phone', 'city', 'state']
    ordering_fields = ['name', 'created_at', 'annual_revenue']
    ordering = ['name']
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get company statistics"""
        total_companies = self.get_queryset().count()
        active_companies = self.get_queryset().filter(is_active=True).count()
        
        # Industry breakdown
        industry_stats = self.get_queryset().values('industry').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'total_companies': total_companies,
            'active_companies': active_companies,
            'industry_breakdown': list(industry_stats)
        })


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_active', 'owner', 'company']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'company__name']
    ordering_fields = ['last_name', 'first_name', 'created_at']
    ordering = ['last_name', 'first_name']
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get contact statistics"""
        total_contacts = self.get_queryset().count()
        active_contacts = self.get_queryset().filter(is_active=True).count()
        
        # Status breakdown
        status_stats = self.get_queryset().values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent contacts (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_contacts = self.get_queryset().filter(created_at__gte=thirty_days_ago).count()
        
        return Response({
            'total_contacts': total_contacts,
            'active_contacts': active_contacts,
            'recent_contacts': recent_contacts,
            'status_breakdown': list(status_stats)
        })


class DealViewSet(viewsets.ModelViewSet):
    queryset = Deal.objects.all()
    serializer_class = DealSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['stage', 'priority', 'is_active', 'owner', 'contact', 'company']
    search_fields = ['name', 'contact__first_name', 'contact__last_name', 'company__name']
    ordering_fields = ['name', 'amount', 'expected_close_date', 'created_at']
    ordering = ['-expected_close_date']
    
    @action(detail=False, methods=['get'])
    def pipeline(self, request):
        """Get pipeline view with deals grouped by stage"""
        pipeline_data = self.get_queryset().values('stage').annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            weighted_amount=Sum('amount') * Avg('probability') / 100
        ).order_by('stage')
        
        return Response(list(pipeline_data))
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get deal statistics"""
        total_deals = self.get_queryset().count()
        active_deals = self.get_queryset().filter(is_active=True).count()
        
        # Total pipeline value
        total_pipeline = self.get_queryset().filter(is_active=True).aggregate(
            total=Sum('amount'),
            weighted=Sum('amount') * Avg('probability') / 100
        )
        
        # Stage breakdown
        stage_stats = self.get_queryset().values('stage').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('stage')
        
        # Recent deals (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_deals = self.get_queryset().filter(created_at__gte=thirty_days_ago).count()
        
        return Response({
            'total_deals': total_deals,
            'active_deals': active_deals,
            'recent_deals': recent_deals,
            'total_pipeline': total_pipeline['total'] or 0,
            'weighted_pipeline': total_pipeline['weighted'] or 0,
            'stage_breakdown': list(stage_stats)
        })


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['activity_type', 'status', 'owner', 'contact', 'company', 'deal']
    search_fields = ['subject', 'description', 'contact__first_name', 'contact__last_name']
    ordering_fields = ['due_date', 'created_at', 'subject']
    ordering = ['-due_date', '-created_at']
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming activities"""
        upcoming = self.get_queryset().filter(
            due_date__gte=timezone.now(),
            status='pending'
        ).order_by('due_date')[:20]
        
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get activity statistics"""
        total_activities = self.get_queryset().count()
        completed_activities = self.get_queryset().filter(status='completed').count()
        pending_activities = self.get_queryset().filter(status='pending').count()
        
        # Activity type breakdown
        type_stats = self.get_queryset().values('activity_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent activities (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_activities = self.get_queryset().filter(created_at__gte=thirty_days_ago).count()
        
        return Response({
            'total_activities': total_activities,
            'completed_activities': completed_activities,
            'pending_activities': pending_activities,
            'recent_activities': recent_activities,
            'type_breakdown': list(type_stats)
        })


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name']
    ordering = ['name']


class PipelineViewSet(viewsets.ModelViewSet):
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class PipelineStageViewSet(viewsets.ModelViewSet):
    queryset = PipelineStage.objects.all()
    serializer_class = PipelineStageSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['pipeline']
    ordering_fields = ['order', 'name']
    ordering = ['pipeline', 'order']


# Tag relationship view sets
class ContactTagViewSet(viewsets.ModelViewSet):
    queryset = ContactTag.objects.all()
    serializer_class = ContactTagSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['contact', 'tag']


class CompanyTagViewSet(viewsets.ModelViewSet):
    queryset = CompanyTag.objects.all()
    serializer_class = CompanyTagSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['company', 'tag']


class DealTagViewSet(viewsets.ModelViewSet):
    queryset = DealTag.objects.all()
    serializer_class = DealTagSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['deal', 'tag']
