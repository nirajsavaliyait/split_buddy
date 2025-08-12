import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

## Send an email using SMTP credentials from environment variables
# Be tolerant when SMTP is not configured: do a no-op instead of crashing app startup.
def send_email(to_email, subject, body):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port_str = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")

    # If SMTP is not configured, log and return without raising
    if not smtp_server or not smtp_username or not smtp_password:
        print("SMTP not configured; skipping email send.")
        return

    try:
        smtp_port = int(smtp_port_str) if smtp_port_str else 587
    except Exception:
        smtp_port = 587

    msg = MIMEMultipart()
    msg["From"] = smtp_username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, to_email, msg.as_string())
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        # Log and continue; do not break request flow in non-critical path
        print(f"Error sending email: {e}")
        return


# import smtplib
# from email.message import EmailMessage

# # This logic sends emails using SMTP
# def send_email(to_email: str, subject: str, body: str):
#     msg = EmailMessage()
#     msg.set_content(body)
#     msg["Subject"] = subject
#     msg["From"] = "nirajsavaliya111@gmail.com"  # Replace with your email
#     msg["To"] = to_email
#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 587) as server:  # Use SMTP_SSL for Gmail
#             server.login("nirajsavaliya111@gmail.com", "cwolehlmtsvnycte")   # Use app password for Gmail
#             server.send_message(msg)
#         print(f"Email sent to {to_email}")
#     except Exception as e:
#         print(f"Failed to send email: {e}")