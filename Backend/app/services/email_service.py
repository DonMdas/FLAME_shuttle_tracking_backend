import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.core.logger import logger
from app.core.config import settings


class EmailService:
    """Service for sending emails (OTP verification, notifications, etc.)"""
    
    def __init__(self):
        # Email configuration - add these to .env file
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', None)
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
        self.from_email = getattr(settings, 'FROM_EMAIL', self.smtp_username)
        self.from_name = getattr(settings, 'FROM_NAME', 'Shuttle Tracker')
    
    def _send_email(self, to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
        """
        Internal method to send email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text fallback (optional)
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        # If SMTP credentials not configured, log OTP to console (development mode)
        if not self.smtp_username or not self.smtp_password:
            logger.warning("SMTP not configured. Email content:")
            logger.warning(f"To: {to_email}")
            logger.warning(f"Subject: {subject}")
            logger.warning(f"Content: {text_content or html_content}")
            return True  # Return success for development
        
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['From'] = f"{self.from_name} <{self.from_email}>"
            message['To'] = to_email
            message['Subject'] = subject
            
            # Attach text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                message.attach(text_part)
            
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_otp_email(self, to_email: str, otp: str) -> bool:
        """
        Send OTP verification email.
        
        Args:
            to_email: Recipient email address
            otp: 6-digit OTP code
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Verify Your Email - Shuttle Tracker"
        
        text_content = f"""
        Hello,
        
        Your OTP for email verification is: {otp}
        
        This OTP will expire in 10 minutes.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        Shuttle Tracker Team
        """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
                .otp-box {{ background-color: white; border: 2px dashed #4CAF50; padding: 20px; text-align: center; margin: 20px 0; border-radius: 5px; }}
                .otp-code {{ font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #4CAF50; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Email Verification</h1>
                </div>
                <div class="content">
                    <p>Hello,</p>
                    <p>Thank you for signing up for Shuttle Tracker. To complete your registration, please verify your email address using the OTP below:</p>
                    
                    <div class="otp-box">
                        <div class="otp-code">{otp}</div>
                    </div>
                    
                    <p><strong>This OTP will expire in 10 minutes.</strong></p>
                    <p>If you didn't request this verification, please ignore this email.</p>
                    
                    <p>Best regards,<br>Shuttle Tracker Team</p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(to_email, subject, html_content, text_content)


# Create a singleton instance
email_service = EmailService()
