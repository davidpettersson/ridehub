from django.conf import settings
from django.core.mail import EmailMultiAlternatives
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
    ) -> None:
        """
        Send an email using a template.

        Args:
            template_name: The name of the template to use (relative to templates/email/)
            context: The context to render the template with
            subject: The subject of the email (will be prefixed with [OBC] if not already)
            recipient_list: List of recipient email addresses
            from_email: The from email address (defaults to settings.EMAIL_FROM)
        """
        # Get the template name without extension
        template_base = template_name.rsplit('.', 1)[0]
        
        # Render the HTML template with the provided context
        html_message = render_to_string(f'email/{template_base}.html', context)
        
        # Also render a plain text version as fallback
        text_message = render_to_string(f'email/{template_base}.txt', context)
        
        # Use default from email if not provided
        if from_email is None:
            from_email = f"Ottawa Bicycle Club <{settings.EMAIL_FROM}>"
            
        # Add [OBC] prefix to subject if not already present
        if not subject.startswith("[OBC]"):
            subject = f"[OBC] {subject}"
            
        # Always use EmailMultiAlternatives to send multipart MIME emails
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=from_email,
            to=recipient_list,
        )
        # Attach the HTML version as an alternative
        email.attach_alternative(html_message, "text/html")
        email.send() 