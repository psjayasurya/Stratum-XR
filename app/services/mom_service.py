import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class MoMService:
    @staticmethod
    def generate_pdf(session_id: str, annotations: list, participants: list, transcripts: list = None) -> BytesIO:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = styles['Heading1']
        story.append(Paragraph(f"Minutes of Meeting - Session {session_id}", title_style))
        story.append(Spacer(1, 12))

        # Date
        normal_style = styles['Normal']
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        story.append(Paragraph(f"Date Generated: {date_str}", normal_style))
        story.append(Spacer(1, 12))

        # Participants
        story.append(Paragraph("<b>Participants:</b>", styles['Heading2']))
        if participants:
            for p in participants:
                story.append(Paragraph(f"- {p}", normal_style))
        else:
            story.append(Paragraph("No participants recorded.", normal_style))
        story.append(Spacer(1, 12))

        # Annotations
        story.append(Paragraph("<b>Annotations & Notes:</b>", styles['Heading2']))
        story.append(Spacer(1, 6))

        if annotations:
            data = [['Type', 'Content', 'Timestamp']]
            for ant in annotations:
                # Handle potential missing keys gracefully
                a_type = ant.get('type', 'General')
                content = ant.get('text', '') or ant.get('content', '')
                ts = ant.get('timestamp', '')
                data.append([a_type, content, ts])

            t = Table(data, colWidths=[80, 300, 100])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('WORDWRAP', (0, 1), (-1, -1), True),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("No annotations recorded during this session.", normal_style))
        story.append(Spacer(1, 12))

        # Transcripts
        story.append(Paragraph("<b>Meeting Transcript:</b>", styles['Heading2']))
        story.append(Spacer(1, 6))

        if transcripts:
            t_data = [['Time', 'Speaker', 'Message']]
            for t in transcripts:
                sender = t.get('sender', 'Unknown')
                msg = t.get('text', '')
                time = t.get('timestamp', '')
                t_data.append([time, sender, msg])
            
            tt = Table(t_data, colWidths=[100, 100, 280])
            tt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.aliceblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('WORDWRAP', (0, 1), (-1, -1), True),
            ]))
            story.append(tt)
        else:
            story.append(Paragraph("No audio transcript available for this session.", normal_style))

        doc.build(story)
        buffer.seek(0)
        return buffer

    @staticmethod
    def send_email(to_emails: list, pdf_buffer: BytesIO, session_id: str):
        if not to_emails:
            raise ValueError("No recipients provided for email")

        sender_email = os.getenv('MAIL_DEFAULT_SENDER')
        sender_password = os.getenv('MAIL_PASSWORD')
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('MAIL_PORT', 587))

        # Validate email configuration
        if not sender_email or not sender_password:
            raise ValueError("Email credentials not configured in .env file")

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(to_emails)
        msg['Subject'] = f"GPR Session MoM - {session_id}"

        body = f"""
        Hello,

        Please find attached the Minutes of Meeting (MoM) for the GPR visualization session {session_id}.
        
        Regards,
        Stratum XR Team
        """
        msg.attach(MIMEText(body, 'plain'))

        # Reset buffer position and attach PDF
        pdf_buffer.seek(0)  # Important: reset to beginning
        pdf_data = pdf_buffer.read()
        pdf_attachment = MIMEApplication(pdf_data, _subtype="pdf")
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=f"MoM_{session_id}.pdf")
        msg.attach(pdf_attachment)

        print(f"Attempting to send email to: {to_emails}")
        print(f"SMTP Server: {smtp_server}:{smtp_port}")
        print(f"From: {sender_email}")

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.set_debuglevel(1)  # Enable debug output
                print("Starting TLS...")
                server.starttls()
                print("Logging in...")
                server.login(sender_email, sender_password)
                print("Sending message...")
                server.send_message(msg)
                print(f"✅ Email sent successfully to {to_emails}")
                return True
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ SMTP Authentication Error: {e}")
            raise Exception(f"Email authentication failed. Please check MAIL_USERNAME and MAIL_PASSWORD in .env file: {str(e)}")
        except smtplib.SMTPException as e:
            print(f"❌ SMTP Error: {e}")
            raise Exception(f"Failed to send email via SMTP: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error sending email: {e}")
            raise Exception(f"Failed to send email: {str(e)}")


mom_service = MoMService()
