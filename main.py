import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

app = FastAPI(title="Espranza Studios API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ContactForm(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    business_name: Optional[str] = None
    message: str


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


@app.post("/contact")
def submit_contact(form: ContactForm):
    """Accept contact form submissions and forward via email if SMTP is configured.
    Fallback: persist to MongoDB if available so nothing is lost.
    """
    # Try email first
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT") or 587)
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user
    to_email = os.getenv("CONTACT_TO_EMAIL") or "hiya@iscuela.com"

    sent_via_email = False
    email_error: Optional[str] = None

    if smtp_host and (smtp_user or smtp_from):
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.utils import formataddr

            body = (
                f"New Contact for Espranza Studios\n\n"
                f"Name: {form.name}\n"
                f"Email: {form.email}\n"
                f"Phone: {form.phone or '-'}\n"
                f"Business: {form.business_name or '-'}\n\n"
                f"Message:\n{form.message}\n"
            )
            msg = MIMEText(body)
            msg['Subject'] = 'New Inquiry – Espranza Studios'
            msg['From'] = formataddr(("Espranza Studios", smtp_from))
            msg['To'] = to_email

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [to_email], msg.as_string())
            sent_via_email = True
        except Exception as e:
            email_error = str(e)

    # Fallback/persistence: store in MongoDB if available
    stored_id = None
    try:
        from database import create_document
        stored_id = create_document("contact", {
            "name": form.name,
            "email": str(form.email),
            "phone": form.phone,
            "business_name": form.business_name,
            "message": form.message,
            "sent_via_email": sent_via_email,
            "email_error": email_error,
        })
    except Exception:
        # Database may be unavailable; ignore
        pass

    if not sent_via_email and not stored_id:
        raise HTTPException(status_code=500, detail="Unable to process contact at this time.")

    return {"ok": True, "sent_via_email": sent_via_email, "stored_id": stored_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
