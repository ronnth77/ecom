from fastapi import BackgroundTasks, UploadFile, File, Form, Depends, HTTPException, status
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import dotenv_values
from pydantic import BaseModel, EmailStr
from typing import List
from models import User
import jwt
import logging

logger = logging.getLogger(__name__)

# Load environment variables
config_credentials = dotenv_values(".env")

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=config_credentials["EMAIL"],
    MAIL_PASSWORD=config_credentials["PASSWORD"],
    MAIL_FROM=config_credentials["EMAIL"],
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,       # instead of MAIL_TLS
    MAIL_SSL_TLS=False,       # instead of MAIL_SSL
    USE_CREDENTIALS=True
)

# Send verification email
async def send_email(email: List[str], instance: User):
    logger.info(f"Generating token data for user: {instance.username}")
    token_data = {
        "id": instance.id,
        "username": instance.username
    }

    # Generate JWT token
    token = jwt.encode(token_data, config_credentials["SECRET"], algorithm="HS256")
    logger.debug(f"Token data generated for user: {instance.username}")
    # Email HTML template
    template = f"""
        <!DOCTYPE html>
        <html>
            <head></head>
            <body>
                <div style="display: flex; align-items: center; justify-content: center; flex-direction: column;">
                    <h3>Account Verification</h3>
                    <p>Thanks for choosing our services. Please click the button below to verify your account:</p>
                    <a style="margin-top: 1rem; padding: 1rem; border-radius: 0.5rem; font-size: 1rem; text-decoration: none;
                    background: #0275d8; color: white;" href="http://localhost:8000/verification/?token={token}">
                        Verify your email
                    </a>
                    <p>If you did not register for our services, please ignore this email.</p>
                </div>
            </body>
        </html>
    """

    message = MessageSchema(
        subject="Verification Email",
        recipients=email,  # must be a list of strings
        body=template,
        subtype="html"
    )
    # LOG sending verification email
    fm = FastMail(conf)
    await fm.send_message(message=message)
    logger.info(f"Verification email sent successfully to {email}")
