from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, SubAdminProfile, UserProfile, ROLE_SUBADMIN, ROLE_USER

@receiver(post_save, sender=CustomUser)
def create_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == ROLE_SUBADMIN:
            SubAdminProfile.objects.create(user=instance, email_address=instance.email)
        elif instance.role == ROLE_USER:
            UserProfile.objects.create(user=instance, email_address=instance.email)