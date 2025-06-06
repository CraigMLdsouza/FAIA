#!/usr/bin/env python3
"""
FAIA: Local Email
A comprehensive AI assistant that can write files and send emails using Ollama and LangChain.
"""

import streamlit as st
import sys
import os
import json
import re
import traceback
import textwrap # Import textwrap for cleaning multiline strings
from tools import file_writer_tool, email_sender_tool # Import tools from local directory
from typing import Dict, Any, List, Optional, Union
from pathlib import Path


# Core imports
try:
    from dotenv import load_dotenv
    from langchain_community.llms import Ollama
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain.prompts import PromptTemplate
    from langchain.tools import Tool
    from langchain_core.agents import AgentAction, AgentFinish # Keep AgentAction, AgentFinish for parsing
except ImportError as e:
    st.error(f"Required packages not installed: {e}")
    st.stop()

# Load environment variables
load_dotenv()

# Debug configuration
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

def debug_log(message: str, level: str = "INFO"):
    """Enhanced debugging with levels"""
    if DEBUG:
        timestamp = st.session_state.get('debug_counter', 0)
        st.session_state.debug_counter = timestamp + 1
        print(f"[DEBUG-{timestamp}] [{level}] {message}")
        if 'debug_messages' not in st.session_state:
            st.session_state.debug_messages = []
        st.session_state.debug_messages.append(f"[{level}] {message}")

def show_debug_info():
    """Display debug information in Streamlit"""
    if DEBUG and 'debug_messages' in st.session_state:
        with st.expander("🐛 Debug Information"):
            for msg in st.session_state.debug_messages[-10:]:  # Show last 10 messages
                st.code(msg, language="text")
#above is fixed

def email_sender_tool(tool_input: Union[str, Dict[str, Any]]) -> str:
    """
    Sends an email with comprehensive error handling.
    
    Args:
        tool_input: Either a JSON string or dict with email parameters
        
    Returns:
        str: Success or error message
    """
    debug_log(f"email_sender_tool called with input: {tool_input}")
    
    try:
        # Parse input
        if isinstance(tool_input, str):
            try:
                params = json.loads(tool_input)
            except json.JSONDecodeError:
                return "❌ ERROR: Invalid JSON format for email parameters"
        elif isinstance(tool_input, dict):
            params = tool_input
        else:
            return f"❌ ERROR: Invalid input format: {type(tool_input)}"
        
        # Extract parameters
        recipient_email = params.get('recipient_email')
        subject = params.get('subject')
        body = params.get('body')
        attachment_path = params.get('attachment_path')
        
        if not recipient_email:
            return "❌ ERROR: Missing 'recipient_email' parameter"
        if not subject:
            return "❌ ERROR: Missing 'subject' parameter"  
        if not body:
            return "❌ ERROR: Missing 'body' parameter"
        
        debug_log(f"Parsed email parameters - recipient: {recipient_email}, subject: {subject}")
        
        try:
            import smtplib
            import ssl
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders
        except ImportError as e:
            error_msg = f"❌ IMPORT ERROR: Required email modules not available: {e}"
            debug_log(error_msg, "ERROR")
            return error_msg
        
        # Get email configuration
        sender_email = os.getenv("EMAIL_ADDRESS")
        app_password = os.getenv("EMAIL_APP_PASSWORD") 
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        
        debug_log(f"Email config - Server: {smtp_server}, Port: {smtp_port}, Sender: {sender_email}")
        
        # Validate configuration
        if not all([sender_email, app_password]):
            error_msg = "❌ CONFIG ERROR: EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be set in .env file"
            debug_log(error_msg, "ERROR")
            return error_msg
        
        # Validate email format (basic) - CORRECTED REGEX
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' # Corrected regex
        if not re.match(email_pattern, recipient_email):
            error_msg = f"❌ VALIDATION ERROR: Invalid recipient email format: {recipient_email}"
            debug_log(error_msg, "ERROR")
            return error_msg
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Attach body
        msg.attach(MIMEText(body, 'plain'))
        debug_log("Email message created successfully")
        
        # Handle attachment if provided
        if attachment_path:
            attachment_path = Path(attachment_path)
            if attachment_path.exists():
                try:
                    with open(attachment_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment_path.name}',
                    )
                    msg.attach(part)
                    debug_log(f"Attachment added: {attachment_path}")
                except Exception as e:
                    debug_log(f"Attachment error: {e}", "WARNING")
                    return f"⚠️ WARNING: Could not attach file '{attachment_path}': {e}. Email sent without attachment."
            else:
                debug_log(f"Attachment file not found: {attachment_path}", "WARNING")
                return f"⚠️ WARNING: Attachment file '{attachment_path}' not found. Email sent without attachment."
        
        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            debug_log("Connecting to SMTP server...")
            server.starttls(context=context)
            debug_log("Starting TLS...")
            server.login(sender_email, app_password)
            debug_log("SMTP login successful")
            
            text = msg.as_string()
            server.sendmail(sender_email, recipient_email, text)
            debug_log("Email sent successfully")
        
        return f"✅ SUCCESS: Email sent to '{recipient_email}' with subject '{subject}'"
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"❌ AUTH ERROR: SMTP authentication failed. Check EMAIL_APP_PASSWORD in .env: {e}"
        debug_log(error_msg, "ERROR")
        return error_msg
    except smtplib.SMTPConnectError as e:
        error_msg = f"❌ CONNECTION ERROR: Cannot connect to SMTP server {smtp_server}:{smtp_port}: {e}"
        debug_log(error_msg, "ERROR")
        return error_msg
    except smtplib.SMTPException as e:
        error_msg = f"❌ SMTP ERROR: {e}"
        debug_log(error_msg, "ERROR")
        return error_msg
    except Exception as e:
        error_msg = f"❌ UNEXPECTED ERROR: {str(e)}"
        debug_log(error_msg, "ERROR")
        return error_msg