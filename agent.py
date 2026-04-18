from llm_ollama import generate_text

def run_agent(question: str, system_prompt: str) -> str:
    return generate_text(system=system_prompt, user=question)