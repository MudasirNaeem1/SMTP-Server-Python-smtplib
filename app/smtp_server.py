from aiosmtpd.controller import Controller
from email import message_from_bytes
import sqlite3
from app import get_db_connection  # Importing connection function


class CustomSMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        msg = message_from_bytes(envelope.content)
        subject = msg.get("Subject", "")
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(
                        part.get_content_charset("utf-8"), errors="replace"
                    )
                    break
        else:
            body = msg.get_payload(decode=True).decode(
                msg.get_content_charset("utf-8"), errors="replace"
            )

        conn = get_db_connection()  # Using the shared connection function
        cursor = conn.cursor()
        for recipient in envelope.rcpt_tos:
            recipient = recipient.strip()
            cursor.execute(
                """
                INSERT INTO inbox (sender, recipient, subject, body)
                VALUES (?, ?, ?, ?)
            """,
                (envelope.mail_from, recipient, subject, body),
            )
        conn.commit()
        conn.close()

        print(
            f"\n📨 Email Received\nFrom: {envelope.mail_from}\nTo: {', '.join(envelope.rcpt_tos)}\nSubject: {subject}\nBody:\n{body}\n"
        )
        return "250 Message accepted for delivery"


if __name__ == "__main__":
    controller = Controller(CustomSMTPHandler(), hostname="localhost", port=1025)
    print("📡 SMTP Server running at localhost:1025")
    controller.start()

    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping SMTP server...")
        controller.stop()
