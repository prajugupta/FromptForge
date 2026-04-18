import ollama

def generate_text(system: str, user: str) -> str:
    response = ollama.chat(
        model="mistral",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )
    return response["message"]["content"]