#!/usr/bin/env python3
"""
AI Council - Query ChatGPT and Gemini in parallel.
Claude response is provided by the calling agent (Clawdbot/Claude).
"""

import sys
import io

# Fix Windows encoding issues
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
import subprocess
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelResponse:
    model: str
    response: str
    success: bool
    error: Optional[str] = None


async def query_codex(question: str, model: str = "gpt-5.2") -> ModelResponse:
    """Query ChatGPT via Codex CLI."""
    try:
        # Use GPT-5.2 explicitly
        proc = await asyncio.create_subprocess_shell(
            f'codex exec -m {model} "{question}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        
        if proc.returncode == 0:
            return ModelResponse("ChatGPT", stdout.decode().strip(), True)
        else:
            return ModelResponse("ChatGPT", "", False, stderr.decode().strip())
    except asyncio.TimeoutError:
        return ModelResponse("ChatGPT", "", False, "Timeout after 120s")
    except Exception as e:
        return ModelResponse("ChatGPT", "", False, str(e))


async def query_gemini(question: str, model: str = "gemini-3-pro-preview") -> ModelResponse:
    """Query Gemini via Gemini CLI."""
    try:
        # Use Gemini 3 Pro Preview (latest/best model)
        proc = await asyncio.create_subprocess_shell(
            f'gemini -p "{question}" -m {model} -o text',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        
        if proc.returncode == 0:
            # Filter out log lines from gemini output
            lines = stdout.decode().strip().split('\n')
            output_lines = [l for l in lines if not l.startswith(('Loaded cached', 'Hook registry'))]
            return ModelResponse("Gemini", '\n'.join(output_lines).strip(), True)
        else:
            return ModelResponse("Gemini", "", False, stderr.decode().strip())
    except asyncio.TimeoutError:
        return ModelResponse("Gemini", "", False, "Timeout after 120s")
    except Exception as e:
        return ModelResponse("Gemini", "", False, str(e))


async def query_all(question: str) -> list[ModelResponse]:
    """Query ChatGPT and Gemini in parallel."""
    tasks = [
        query_codex(question),
        query_gemini(question),
    ]
    return await asyncio.gather(*tasks)


def format_json(responses: list[ModelResponse], question: str) -> str:
    """Format as JSON for Clawdbot to process."""
    return json.dumps({
        "question": question,
        "responses": [
            {
                "model": r.model,
                "success": r.success,
                "response": r.response if r.success else None,
                "error": r.error if not r.success else None
            }
            for r in responses
        ]
    }, indent=2)


async def main():
    if len(sys.argv) < 2:
        print("Usage: council.py <question>")
        print("Returns JSON with ChatGPT and Gemini responses.")
        print("Claude response should be provided by the calling agent.")
        sys.exit(1)
    
    question = sys.argv[1]
    
    print(f"Querying ChatGPT and Gemini...", file=sys.stderr)
    
    responses = await query_all(question)
    
    print(format_json(responses, question))


if __name__ == "__main__":
    asyncio.run(main())
