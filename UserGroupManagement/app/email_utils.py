import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


# Send an email using SMTP credentials from environment variables
def send_email(to_email, subject, body):
    # Get SMTP configuration from environment
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")

    # Create the email message
    msg = MIMEMultipart()
    msg["From"] = smtp_username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        # Connect to SMTP server and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, to_email, msg.as_string())
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        # Print and raise error if sending fails
        print(f"Error sending email: {e}")
        raise