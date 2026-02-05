"""
RBAC and team-based visibility helpers.
Uses Django Group names: Admin, Sales Manager, Sales Rep, Viewer.
"""

from django.contrib.auth.models import Group
from django.db.models import Q

ROLE_GROUPS = ("Admin", "Sales Manager", "Sales Rep", "Viewer")


def get_user_team(user):
    """Return the team for user (from UserProfile) or None."""
    if not user or not user.is_authenticated:
        return None
    try:
        return user.profile.team
    except Exception:
        return None


def user_is_admin(user):
    """User is in Admin group or is staff."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    return user.groups.filter(name="Admin").exists()


def user_is_viewer_only(user):
    """User is in Viewer group and not in any higher role."""
    if not user or not user.is_authenticated:
        return False
    if user_is_admin(user):
        return False
    if user.groups.filter(name__in=("Sales Manager", "Sales Rep")).exists():
        return False
    return user.groups.filter(name="Viewer").exists()


def user_can_view_entity(user, entity, owner_field="owner"):
    """Return True if user can view this entity (same visibility as list)."""
    if user_can_edit_entity(user, entity, owner_field):
        return True
    if user_is_viewer_only(user):
        owner = getattr(entity, owner_field, None)
        return owner is not None and owner.pk == user.pk
    return False


def user_can_edit_entity(user, entity, owner_field="owner"):
    """Return True if user can edit this entity (contact, company, deal, etc.)."""
    if not user or not user.is_authenticated:
        return False
    if user_is_admin(user):
        return True
    if user_is_viewer_only(user):
        return False
    owner = getattr(entity, owner_field, None)
    if owner is None:
        return True
    if owner.pk == user.pk:
        return True
    if user.groups.filter(name="Sales Manager").exists():
        team = get_user_team(user)
        if (
            team
            and hasattr(owner, "profile")
            and getattr(owner.profile, "team_id", None) == team.pk
        ):
            return True
    return False


def filter_queryset_by_team(qs, user, owner_field="owner"):
    """Restrict queryset to records the user is allowed to see (by team/ownership)."""
    if not user or not user.is_authenticated:
        return qs.none()
    if user_is_admin(user):
        return qs
    team = get_user_team(user)
    if user.groups.filter(name="Sales Manager").exists() and team:
        return qs.filter(**{f"{owner_field}__profile__team": team})
    return qs.filter(**{owner_field: user})
