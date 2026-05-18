"""gita_gnana_server.py
MCP server that loads a PDF (Bhagavad Gita explanation) and provides tools:
- get_pdf_text(): returns the full text of the PDF
- answer(question: str): uses the LLM to answer a question based on the loaded PDF source.
- update_system_prompt(new_prompt): updates the system prompt used for answering.
The server respects a system prompt stored in 'system_prompt.txt' which can be edited at runtime.
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from pypdf import PdfReader

from mcp.server.fastmcp import FastMCP

# Load configuration from environment variables
PDF_PATH = os.getenv('GITA_PDF_PATH', 'C://Users/Chakri/Downloads/bhagavad-gita-in-english-source-file.pdf')  # path to the PDF file

# Helper functions to load sources
def load_pdf_text(path: str) -> str:
    try:
        reader = PdfReader(path)
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or "")
        return "\n".join(text)
    except Exception as e:
        return f"[Error reading PDF: {e}]"

# Global variables for lazy loading
PDF_TEXT_CACHE = None

def get_pdf_text_content() -> str:
    global PDF_TEXT_CACHE
    if PDF_TEXT_CACHE is None:
        PDF_TEXT_CACHE = load_pdf_text(PDF_PATH)
    return PDF_TEXT_CACHE

# =====================================================================
# SYSTEM PROMPT
# Add or paste your system prompt directly between the triple quotes below!
# =====================================================================
SYSTEM_PROMPT = """You are an AI assistant whose sole knowledge base consists of the provided PDF document explaining the Bhagavad Gita. 

You must ONLY use this source to answer questions. Do not rely on outside knowledge or invent information. If the answer is not present in the source, explicitly state: "This is not covered in the provided source."

### Reasoning Instructions
- Always think step-by-step before answering.
- Explain your reasoning clearly and logically.
- Separate reasoning from the final answer.

### Output Format
Respond in the following JSON structure:

{
  "reasoning_steps": [
    "Step 1: Identify relevant sections in the sources",
    "Step 2: Extract key ideas",
    "Step 3: Connect ideas to the user’s question"
  ],
  "answer": "Final concise answer in plain text",
  "reasoning_type": "logic | ethics | philosophy | lookup | interpretation",
  "self_check": "Verification of consistency with sources",
  "fallback": "If uncertain, state clearly that the sources do not provide enough information"
}

### Rules
1. **Tool Separation**: Reasoning must be distinct from any lookup or computation.
2. **Conversation Loop**: Support multi-turn dialogue by remembering context from previous questions.
3. **Instructional Framing**: Always follow the JSON format above.
4. **Internal Self-Checks**: Before finalizing, verify that the answer matches the sources and does not hallucinate.
5. **Reasoning Type Awareness**: Tag the reasoning type used (e.g., ethics, logic, philosophy).
6. **Error Handling**: If unsure or sources are silent, respond with fallback message.
7. **Clarity**: Keep answers concise, relevant, and easy to parse.
8. **Source Anchoring**: Always reference where in the PDF the reasoning is drawn from.
9. **No External Knowledge**: Never use outside information, even if relevant — restrict strictly to the provided PDF.
10. **Consistency Check**: Ensure consistency and clear perspective from the PDF.
11. **Transparency**: Explicitly state when an interpretation is inferred rather than directly quoted.
12. **Ethical Sensitivity**: When answering questions on mental health, ethics, or wellbeing, emphasize that guidance is philosophical, not medical advice.
13. **User Context Awareness**: Adapt answers to real-world scenarios but always tie back to the Gita’s teachings.
14. **Fallback Expansion**: If uncertain, suggest the user revisit specific chapters or verses in the PDF for clarity.
15. **Formatting Discipline**: Never break JSON structure; ensure predictable parsing.

### Example
User: "How does the Gita guide us on selflessness?"
Response:
{
  "reasoning_steps": [
    "Step 1: Locate verses on karma yoga in the PDF",
    "Step 2: Identify teachings on acting without desire for fruits",
    "Step 3: Connect this to modern idea of selflessness"
  ],
  "answer": "The Gita teaches selflessness through karma yoga, emphasizing action without attachment to results.",
  "reasoning_type": "ethics",
  "self_check": "Verified against the PDF; consistent with karma yoga explanation",
  "fallback": "Not needed",
  "source_anchor": "PDF Chapter 3"
}
"""

# MCP server definition
mcp = FastMCP("gita-gnana-server")

@mcp.tool()
def get_pdf_text() -> str:
    """Return the extracted text of the configured PDF."""
    return get_pdf_text_content()



@mcp.tool()
def answer(question: str) -> str:
    """Answer a user question using the LLM with the PDF as context."""
    # Truncate sources for prompt size safety
    pdf_text = get_pdf_text_content()
    
    pdf_chunk = pdf_text[:3000] + ("..." if len(pdf_text) > 3000 else "")
    system = SYSTEM_PROMPT
    prompt = (
        f"{system}\n\n"
        f"--- PDF EXTRACT (truncated) ---\n{pdf_chunk}\n\n"
        f"Question: {question}\nAnswer:"
    )

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Error: No GEMINI_API_KEY found in environment."

    # Use gemini-2.5-flash as requested by the user
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    import time
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 503 and attempt < 2:
                time.sleep(2)  # Wait 2 seconds before retrying
                continue
            return f"Error calling Gemini API: {e}\nResponse: {resp.text}"
        except Exception as e:
            return f"Error calling Gemini API: {e}"

@mcp.tool()
def update_system_prompt(new_prompt: str) -> str:
    """Replace the system prompt used by the answer tool. Returns the previous prompt."""
    global SYSTEM_PROMPT
    old = SYSTEM_PROMPT
    SYSTEM_PROMPT = new_prompt
    return old

if __name__ == "__main__":
    import sys
    # Check for API key and warn if missing
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("Warning: No LLM API key found in environment variables.", file=sys.stderr)
    
    # Run the server. Defaulting to SSE for better performance with web clients.
    # Use transport="stdio" if running from a CLI client.
    mode = os.getenv("MCP_TRANSPORT", "stdio")
    print(f"Starting Gita Gnana Server in {mode} mode...", file=sys.stderr)
    mcp.run(transport=mode)
