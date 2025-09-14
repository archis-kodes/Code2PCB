import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# Load OpenAI key from .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize LangChain OpenAI client
llm = ChatOpenAI(
    model="gpt-4o-mini",  # fast + accurate
    temperature=0.2,
    api_key=OPENAI_API_KEY
)

SYSTEM_PROMPT = """
You are an expert embedded systems and PCB design assistant.
Your task: Given Arduino (.ino) code and a microcontroller/board,
return all required PCB information in valid JSON.

Output MUST strictly follow this schema:

{
  "components": [
    {"name": "string", "type": "string", "footprint": "string"}
  ],
  "connections": [
    {"from": "string", "to": "string"}
  ],
  "power": {
    "voltage": "string",
    "regulator": "string"
  }
}
"""

def analyze_code(ino_file_path: str, chip_name: str):
    """
    Dynamically analyze any uploaded .ino file and return JSON with PCB components & connections.

    Parameters:
    - ino_file_path: path to uploaded Arduino sketch
    - chip_name: MCU/board name returned by compile.py
    """
    # Read the uploaded .ino file
    with open(ino_file_path, "r") as f:
        ino_code = f.read()

    # Step 1: ask model for PCB JSON
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Target board/chip: {chip_name}\n\nArduino code:\n\n{ino_code}")
    ]

    response = llm.invoke(messages)
    raw_text = response.content

    # Step 2: try parsing JSON
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Step 3: retry asking model to fix JSON strictly
        fix_messages = [
            SystemMessage(content="You are a strict JSON fixer."),
            HumanMessage(content=f"Fix the following text into valid JSON matching the schema:\n\n{raw_text}")
        ]
        retry_text = llm.invoke(fix_messages).content

        try:
            return json.loads(retry_text)
        except json.JSONDecodeError:
            # Fallback: return raw response
            return {"raw_response": raw_text}
