# szn_site/core/custom_email_backend.py
import smtplib
import ssl
import certifi
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

class CustomSMTPEmailBackend(BaseEmailBackend):
    def __init__(self, host=None, port=None, username=None, password=None,
                 use_tls=None, fail_silently=False, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.host = host or settings.EMAIL_HOST
        self.port = port or settings.EMAIL_PORT
        # Use Django standard naming
        self.username = username or getattr(settings, 'EMAIL_HOST_USER', '')
        self.password = password or getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        self.use_tls = use_tls if use_tls is not None else getattr(settings, 'EMAIL_USE_TLS', False)
        self.timeout = timeout or getattr(settings, 'EMAIL_TIMEOUT', None)
        self.connection = None

    def open(self):
        """Open an SMTP connection."""
        if self.connection:
            return False  # Already open
        
        try:
            print(f"DEBUG: Opening connection to {self.host}:{self.port}")
            
            # Create connection
            self.connection = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            
            # Say hello
            self.connection.ehlo()
            
            # Start TLS if needed
            if self.use_tls:
                print("DEBUG: Starting TLS")
                context = ssl.create_default_context(cafile=certifi.where())
                self.connection.starttls(context=context)
                self.connection.ehlo()  # Re-ehlo after TLS
            
            # Login if credentials provided
            if self.username and self.password:
                print(f"DEBUG: Logging in as {self.username}")
                self.connection.login(self.username, self.password)
            
            print("DEBUG: Connection opened successfully")
            return True
            
        except Exception as e:
            print(f"DEBUG: Failed to open connection: {str(e)}")
            self.connection = None
            if not self.fail_silently:
                raise
            return False

    def close(self):
        """Close the SMTP connection."""
        if self.connection is None:
            return
        
        try:
            print("DEBUG: Closing connection")
            self.connection.quit()
        except Exception:
            if not self.fail_silently:
                raise
        finally:
            self.connection = None

    def send_messages(self, email_messages):
        """Send one or more EmailMessage objects and return the number sent."""
        if not email_messages:
            print("DEBUG: No messages to send")
            return 0
        
        print(f"DEBUG: Attempting to send {len(email_messages)} email(s)")
        
        num_sent = 0
        
        # Try to open connection
        if not self.open():
            print("DEBUG: Could not open connection")
            return num_sent
        
        try:
            for i, email_message in enumerate(email_messages):
                try:
                    print(f"DEBUG: Sending email {i+1}/{len(email_messages)}")
                    print(f"DEBUG: Subject: {email_message.subject}")
                    print(f"DEBUG: To: {email_message.to}")
                    
                    sent = self._send(email_message)
                    if sent:
                        num_sent += 1
                        print(f"DEBUG: ✓ Email sent successfully")
                    else:
                        print(f"DEBUG: ✗ Failed to send email")
                        
                except Exception as e:
                    print(f"DEBUG: Error sending email {i+1}: {str(e)}")
                    if not self.fail_silently:
                        raise
                    # Continue with next email if fail_silently is True
        
        finally:
            # Always close the connection
            self.close()
        
        print(f"DEBUG: Total emails sent: {num_sent}/{len(email_messages)}")
        return num_sent

    def _send(self, email_message):
        """Send a single email message."""
        if not email_message.recipients():
            print("DEBUG: No recipients")
            return False
        
        try:
            # Create message
            msg = email_message.message()
            
            # Send it
            self.connection.sendmail(
                email_message.from_email,
                email_message.recipients(),
                msg.as_string()
            )
            return True
            
        except smtplib.SMTPException as e:
            print(f"DEBUG: SMTP error: {str(e)}")
            if not self.fail_silently:
                raise
            return False
        except Exception as e:
            print(f"DEBUG: General error: {str(e)}")
            if not self.fail_silently:
                raise
            return False