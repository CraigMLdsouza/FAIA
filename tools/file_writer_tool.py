#!/usr/bin/env python3
"""
FAIA: File Assistant
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

def file_writer_tool(tool_input: Union[str, Dict[str, Any]]) -> str:
    """
    Writes content to a local text file with comprehensive error handling.
    
    Args:
        tool_input: Either a JSON string or dict with 'file_path' and 'content' keys
        
    Returns:
        str: Success or error message
    """
    debug_log(f"file_writer_tool called with input: {tool_input}")
    
    try:
        # Parse input
        if isinstance(tool_input, str):
            try:
                # Try to parse as JSON
                params = json.loads(tool_input)
            except json.JSONDecodeError:
                # If not JSON, assume it's just the file path and we need content
                return "❌ ERROR: Missing content parameter. Please provide both file_path and content."
        elif isinstance(tool_input, dict):
            params = tool_input
        else:
            return f"❌ ERROR: Invalid input format: {type(tool_input)}"
        
        # Extract parameters
        file_path = params.get('file_path')
        content = params.get('content')
        
        if not file_path:
            return "❌ ERROR: Missing 'file_path' parameter"
        if not content:
            return "❌ ERROR: Missing 'content' parameter"
        
        debug_log(f"Parsed parameters - file_path: {file_path}, content length: {len(content)}")
        
        # Convert to Path object for better handling
        path_obj = Path(file_path)
        abs_path = path_obj.resolve()
        
        debug_log(f"Absolute path: {abs_path}")
        
        # Create parent directories if they don't exist
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        debug_log(f"Created parent directories for: {abs_path.parent}")
        
        # Write the file
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        debug_log(f"Successfully wrote {len(content)} characters to file")
        return f"✅ SUCCESS: Content written to '{file_path}' ({len(content)} characters)"
        
    except PermissionError as e:
        error_msg = f"❌ PERMISSION ERROR: Cannot write to '{file_path}'. Check file permissions."
        debug_log(error_msg, "ERROR")
        return error_msg
    except OSError as e:
        error_msg = f"❌ OS ERROR: {str(e)}"
        debug_log(error_msg, "ERROR") 
        return error_msg
    except Exception as e:
        error_msg = f"❌ UNEXPECTED ERROR: {str(e)}"
        debug_log(error_msg, "ERROR")
        return error_msg
