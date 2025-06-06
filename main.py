#!/usr/bin/env python3
"""
FAIA: Local Email & File Assistant
A comprehensive AI assistant that can write files and send emails using Ollama and LangChain.
"""

import streamlit as st
import sys
import os
import json
import re
import traceback
import textwrap # Import textwrap for cleaning multiline strings
from tools.file_writer_tool import file_writer_tool
from tools.email_sender_tool import email_sender_tool # Import tools from local directory
from typing import Dict, Any, List, Optional, Union
from pathlib import Path


# Add tools directory to Python path
tools_dir = Path(__file__).parent / "tools"
sys.path.append(str(tools_dir))

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

# Configure Streamlit
st.set_page_config(
    page_title="FAIA Assistant",
    page_icon="🤖",
    layout="wide"
)

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

#tools
# def file_writer_tool(tool_input: Union[str, Dict[str, Any]]) -> str:
#     """
#     Writes content to a local text file with comprehensive error handling.
    
#     Args:
#         tool_input: Either a JSON string or dict with 'file_path' and 'content' keys
        
#     Returns:
#         str: Success or error message
#     """
#     debug_log(f"file_writer_tool called with input: {tool_input}")
    
#     try:
#         # Parse input
#         if isinstance(tool_input, str):
#             try:
#                 # Try to parse as JSON
#                 params = json.loads(tool_input)
#             except json.JSONDecodeError:
#                 # If not JSON, assume it's just the file path and we need content
#                 return "❌ ERROR: Missing content parameter. Please provide both file_path and content."
#         elif isinstance(tool_input, dict):
#             params = tool_input
#         else:
#             return f"❌ ERROR: Invalid input format: {type(tool_input)}"
        
#         # Extract parameters
#         file_path = params.get('file_path')
#         content = params.get('content')
        
#         if not file_path:
#             return "❌ ERROR: Missing 'file_path' parameter"
#         if not content:
#             return "❌ ERROR: Missing 'content' parameter"
        
#         debug_log(f"Parsed parameters - file_path: {file_path}, content length: {len(content)}")
        
#         # Convert to Path object for better handling
#         path_obj = Path(file_path)
#         abs_path = path_obj.resolve()
        
#         debug_log(f"Absolute path: {abs_path}")
        
#         # Create parent directories if they don't exist
#         abs_path.parent.mkdir(parents=True, exist_ok=True)
#         debug_log(f"Created parent directories for: {abs_path.parent}")
        
#         # Write the file
#         with open(abs_path, 'w', encoding='utf-8') as f:
#             f.write(content)
        
#         debug_log(f"Successfully wrote {len(content)} characters to file")
#         return f"✅ SUCCESS: Content written to '{file_path}' ({len(content)} characters)"
        
#     except PermissionError as e:
#         error_msg = f"❌ PERMISSION ERROR: Cannot write to '{file_path}'. Check file permissions."
#         debug_log(error_msg, "ERROR")
#         return error_msg
#     except OSError as e:
#         error_msg = f"❌ OS ERROR: {str(e)}"
#         debug_log(error_msg, "ERROR") 
#         return error_msg
#     except Exception as e:
#         error_msg = f"❌ UNEXPECTED ERROR: {str(e)}"
#         debug_log(error_msg, "ERROR")
#         return error_msg

# def email_sender_tool(tool_input: Union[str, Dict[str, Any]]) -> str:
    # """
    # Sends an email with comprehensive error handling.
    
    # Args:
    #     tool_input: Either a JSON string or dict with email parameters
        
    # Returns:
    #     str: Success or error message
    # """
    # debug_log(f"email_sender_tool called with input: {tool_input}")
    
    # try:
    #     # Parse input
    #     if isinstance(tool_input, str):
    #         try:
    #             params = json.loads(tool_input)
    #         except json.JSONDecodeError:
    #             return "❌ ERROR: Invalid JSON format for email parameters"
    #     elif isinstance(tool_input, dict):
    #         params = tool_input
    #     else:
    #         return f"❌ ERROR: Invalid input format: {type(tool_input)}"
        
    #     # Extract parameters
    #     recipient_email = params.get('recipient_email')
    #     subject = params.get('subject')
    #     body = params.get('body')
    #     attachment_path = params.get('attachment_path')
        
    #     if not recipient_email:
    #         return "❌ ERROR: Missing 'recipient_email' parameter"
    #     if not subject:
    #         return "❌ ERROR: Missing 'subject' parameter"  
    #     if not body:
    #         return "❌ ERROR: Missing 'body' parameter"
        
    #     debug_log(f"Parsed email parameters - recipient: {recipient_email}, subject: {subject}")
        
    #     try:
    #         import smtplib
    #         import ssl
    #         from email.mime.text import MIMEText
    #         from email.mime.multipart import MIMEMultipart
    #         from email.mime.base import MIMEBase
    #         from email import encoders
    #     except ImportError as e:
    #         error_msg = f"❌ IMPORT ERROR: Required email modules not available: {e}"
    #         debug_log(error_msg, "ERROR")
    #         return error_msg
        
    #     # Get email configuration
    #     sender_email = os.getenv("EMAIL_ADDRESS")
    #     app_password = os.getenv("EMAIL_APP_PASSWORD") 
    #     smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    #     smtp_port = int(os.getenv("SMTP_PORT", "587"))
        
    #     debug_log(f"Email config - Server: {smtp_server}, Port: {smtp_port}, Sender: {sender_email}")
        
    #     # Validate configuration
    #     if not all([sender_email, app_password]):
    #         error_msg = "❌ CONFIG ERROR: EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be set in .env file"
    #         debug_log(error_msg, "ERROR")
    #         return error_msg
        
    #     # Validate email format (basic) - CORRECTED REGEX
    #     email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' # Corrected regex
    #     if not re.match(email_pattern, recipient_email):
    #         error_msg = f"❌ VALIDATION ERROR: Invalid recipient email format: {recipient_email}"
    #         debug_log(error_msg, "ERROR")
    #         return error_msg
        
    #     # Create message
    #     msg = MIMEMultipart()
    #     msg['From'] = sender_email
    #     msg['To'] = recipient_email
    #     msg['Subject'] = subject
        
    #     # Attach body
    #     msg.attach(MIMEText(body, 'plain'))
    #     debug_log("Email message created successfully")
        
    #     # Handle attachment if provided
    #     if attachment_path:
    #         attachment_path = Path(attachment_path)
    #         if attachment_path.exists():
    #             try:
    #                 with open(attachment_path, "rb") as attachment:
    #                     part = MIMEBase('application', 'octet-stream')
    #                     part.set_payload(attachment.read())
                    
    #                 encoders.encode_base64(part)
    #                 part.add_header(
    #                     'Content-Disposition',
    #                     f'attachment; filename= {attachment_path.name}',
    #                 )
    #                 msg.attach(part)
    #                 debug_log(f"Attachment added: {attachment_path}")
    #             except Exception as e:
    #                 debug_log(f"Attachment error: {e}", "WARNING")
    #                 return f"⚠️ WARNING: Could not attach file '{attachment_path}': {e}. Email sent without attachment."
    #         else:
    #             debug_log(f"Attachment file not found: {attachment_path}", "WARNING")
    #             return f"⚠️ WARNING: Attachment file '{attachment_path}' not found. Email sent without attachment."
        
    #     # Send email
    #     context = ssl.create_default_context()
    #     with smtplib.SMTP(smtp_server, smtp_port) as server:
    #         debug_log("Connecting to SMTP server...")
    #         server.starttls(context=context)
    #         debug_log("Starting TLS...")
    #         server.login(sender_email, app_password)
    #         debug_log("SMTP login successful")
            
    #         text = msg.as_string()
    #         server.sendmail(sender_email, recipient_email, text)
    #         debug_log("Email sent successfully")
        
    #     return f"✅ SUCCESS: Email sent to '{recipient_email}' with subject '{subject}'"
        
    # except smtplib.SMTPAuthenticationError as e:
    #     error_msg = f"❌ AUTH ERROR: SMTP authentication failed. Check EMAIL_APP_PASSWORD in .env: {e}"
    #     debug_log(error_msg, "ERROR")
    #     return error_msg
    # except smtplib.SMTPConnectError as e:
    #     error_msg = f"❌ CONNECTION ERROR: Cannot connect to SMTP server {smtp_server}:{smtp_port}: {e}"
    #     debug_log(error_msg, "ERROR")
    #     return error_msg
    # except smtplib.SMTPException as e:
    #     error_msg = f"❌ SMTP ERROR: {e}"
    #     debug_log(error_msg, "ERROR")
    #     return error_msg
    # except Exception as e:
    #     error_msg = f"❌ UNEXPECTED ERROR: {str(e)}"
    #     debug_log(error_msg, "ERROR")
    #     return error_msg

# Initialize tools
def create_tools() -> List[Tool]:
    """Create and return list of available tools"""
    tools = [
        Tool(
            name="file_writer_tool",
            func=file_writer_tool,
            description="Writes content to a local text file. Input should be JSON with keys: file_path (str), content (str). Example: {'file_path': 'test.txt', 'content': 'Hello World'}"
        ),
        Tool(
            name="email_sender_tool", 
            func=email_sender_tool,
            description="Sends an email to a recipient. Input should be JSON with keys: recipient_email (str), subject (str), body (str), attachment_path (str, optional). Example: {'recipient_email': 'user@example.com', 'subject': 'Hello', 'body': 'Test email', 'attachment_path': 'file.txt'}"
        )
    ]
    debug_log(f"Created {len(tools)} tools")
    return tools

# LLM and Agent Setup
@st.cache_resource
def create_agent_executor():
    """Create and cache the agent executor"""
    debug_log("Creating agent executor...")
    
    try:
        # Initialize LLM
        llm = Ollama(
            model="deepseek-r1:8b",
            temperature=0.1,
            verbose=DEBUG
        )
        debug_log("LLM initialized successfully")
        
        # Test LLM connection
        try:
            test_response = llm.invoke("Hello")
            debug_log(f"LLM test successful: {test_response[:50]}...")
        except Exception as e:
            debug_log(f"LLM test failed: {e}", "ERROR")
            raise Exception(f"Cannot connect to Ollama. Make sure it's running with 'ollama serve' and model is pulled: {e}")
        
        # Create tools
        tools = create_tools()
        
        # Create prompt template - IMPROVED VERSION
        prompt_template = textwrap.dedent("""
            You are FAIA, a helpful AI assistant that can use tools to complete tasks for users.

            You have access to the following tools:
            {tools}

            Tool names: {tool_names}

            You MUST use the following format exactly - do not deviate from this format:

            Thought: I need to understand what the user is asking for and determine which tool to use.
            Action: [choose from: {tool_names}]
            Action Input: [JSON string with the required parameters]
            Observation: [the result of the action will appear here]
            ... (repeat Thought/Action/Action Input/Observation as needed)
            Thought: I now have completed the task and can provide the final answer.
            Final Answer: [your final response to the user]

            CRITICAL RULES:
            1. Action Input MUST be valid JSON - no extra text, no markdown formatting
            2. You MUST actually execute actions using the tools - don't just describe what should be done
            3. For email_sender_tool, you MUST provide recipient_email, subject, and body
            4. For file_writer_tool, you MUST provide file_path and content
            5. Always complete the full ReAct cycle - don't skip to Final Answer without using tools

            Examples:
            - For file writing: Action Input: {{"file_path": "example.txt", "content": "Hello world"}}
            - For email sending: Action Input: {{"recipient_email": "user@example.com", "subject": "Test", "body": "Hello there"}}

            Begin!

            Question: {input}
            Thought: {agent_scratchpad}""")

        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"]
        )
        debug_log("Prompt template created")
        
        # Create agent
        agent = create_react_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
        debug_log("Agent created successfully")
        
        # Create agent executor with stricter error handling
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=DEBUG,
            handle_parsing_errors="CRITICAL ERROR: You must follow the exact format: 'Thought:', 'Action:', 'Action Input:', 'Observation:', 'Final Answer:'. Action Input must be valid JSON. You cannot skip using tools - you must actually execute the action, not just describe it.",
            max_iterations=5,
            early_stopping_method="force",
            return_intermediate_steps=True
        )
        debug_log("Agent executor created successfully")
        
        return agent_executor, tools
        
    except Exception as e:
        debug_log(f"Failed to create agent: {e}", "ERROR")
        raise e

# Streamlit UI
def main():
    """Main Streamlit application"""
    
    # Initialize session state
    if 'debug_messages' not in st.session_state:
        st.session_state.debug_messages = []
    if 'debug_counter' not in st.session_state:
        st.session_state.debug_counter = 0
    
    # Header
    st.title("🤖 FAIA: Local Email & File Assistant")
    st.markdown("### Your AI assistant for file operations and email management")
    
    # Configuration status
    with st.expander("📋 System Status & Configuration"):
        st.subheader("Environment Setup")
        
        # Check Ollama
        try:
            # Use the same model as the agent for consistency
            test_llm = Ollama(model="deepseek-r1:8b")
            test_response = test_llm.invoke("test")
            st.success("✅ Ollama connection successful")
        except Exception as e:
            st.error(f"❌ Ollama connection failed: {e}")
            st.info("Make sure Ollama is running: `ollama serve` and model is pulled: `ollama pull deepseek-r1:8b`")
        
        # Check email config
        email_configured = bool(os.getenv("EMAIL_ADDRESS")) and bool(os.getenv("EMAIL_APP_PASSWORD"))
        if email_configured:
            st.success(f"✅ Email configured for: {os.getenv('EMAIL_ADDRESS')}")
        else:
            st.warning("⚠️ Email not configured. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env file")
        
        # Debug toggle
        debug_enabled = st.checkbox("Enable Debug Mode", value=DEBUG)
        if debug_enabled != DEBUG:
            st.info("Debug mode setting will take effect on next restart")
    
    # Create agent
    try:
        with st.spinner("Initializing FAIA..."):
            agent_executor, tools = create_agent_executor()
        
        # Show available tools
        st.subheader("🛠️ Available Tools")
        for tool in tools:
            st.write(f"**{tool.name}**: {tool.description}")
        
        # Main interface
        st.subheader("💬 Chat with FAIA")
        
        # User input
        user_query = st.text_area(
            "What would you like FAIA to help you with?",
            height=120,
            placeholder="Examples:\n- Write a report to report.txt\n- Send an email to someone@example.com about project updates\n- Create a file with meeting notes"
        )
        
        # Execution buttons
        col1, col2 = st.columns([1, 4])
        with col1:
            execute_button = st.button("🚀 Execute Task", type="primary")
        with col2:
            clear_debug = st.button("🧹 Clear Debug")
            if clear_debug:
                st.session_state.debug_messages = []
                st.rerun()
        
        # Execute task
        if execute_button and user_query:
            st.subheader("🧠 FAIA's Processing")
            
            with st.spinner("FAIA is working on your request..."):
                try:
                    debug_log(f"Executing user query: {user_query}")
                    
                    # Execute the agent
                    response = agent_executor.invoke({"input": user_query})
                    
                    debug_log(f"Agent response: {response}")
                    
                    # Display result
                    st.subheader("✨ Result")
                    if isinstance(response, dict) and "output" in response:
                        st.success(response["output"])
                        
                        # Show intermediate steps if available
                        if "intermediate_steps" in response and response["intermediate_steps"]:
                            with st.expander("🔍 Processing Steps"):
                                for i, (action, observation) in enumerate(response["intermediate_steps"]):
                                    st.write(f"**Step {i+1}:**")
                                    st.write(f"- Action: {action.tool}")
                                    st.write(f"- Input: {action.tool_input}")
                                    st.write(f"- Result: {observation}")
                                    st.write("---")
                    else:
                        st.success(str(response))
                            
                except Exception as e:
                    debug_log(f"Execution error: {str(e)}", "ERROR")
                    st.error(f"❌ Error executing task: {str(e)}")
                    
                    # Show detailed error in debug mode
                    if DEBUG:
                        st.subheader("🐛 Detailed Error Information")
                        st.code(traceback.format_exc(), language="python")
        
        elif execute_button and not user_query:
            st.warning("⚠️ Please enter a request for FAIA")
        
        # Debug information
        show_debug_info()
        
    except Exception as e:
        st.error(f"❌ Failed to initialize FAIA: {str(e)}")
        st.subheader("🔧 Troubleshooting")
        st.write("1. Make sure Ollama is running: `ollama serve`")
        st.write("2. Make sure the model is pulled: `ollama pull deepseek-r1:8b`")
        st.write("3. Check your .env file configuration")
        st.write("4. Ensure all required packages are installed")
        
        if DEBUG:
            st.subheader("🐛 Detailed Error")
            st.code(traceback.format_exc(), language="python")

# Run the application
if __name__ == "__main__":
    main()