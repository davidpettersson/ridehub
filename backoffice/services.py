from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from typing import List, Optional, Dict, Any


class EmailService:
    """
    Service for sending emails using templates.
    All email content should be defined in templates instead of hardcoded strings.
    """

    @classmethod
    def send_email(
        cls,
        template_name: str,
        context: Dict[str, Any],
        subject: str,
        recipient_list: List[str],
        from_email: Optional[str] = None,
        bcc: Optional[List[str]] = None,
    ) -> None:
        """
        Send an email using a template.

        Args:
            template_name: The name of the template to use (relative to templates/email/)
            context: The context to render the template with
            subject: The subject of the email
            recipient_list: List of recipient email addresses
            from_email: The from email address (defaults to settings.EMAIL_FROM)
            bcc: List of BCC email addresses
        """
        # Render the template with the provided context
        message = render_to_string(f'email/{template_name}', context)
        
        # Use default from email if not provided
        if from_email is None:
            from_email = f"Ottawa Bicycle Club <{settings.EMAIL_FROM}>"
            
        # Send the email
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            bcc=bcc or [],
        ) 