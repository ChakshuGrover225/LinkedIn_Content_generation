import anthropic
import settings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

local_setting = settings.Linkedin_content_generator_SettingClass

print(settings.settings.linkedin_content_generator_setting.writer_prompt_path)
print(settings.settings.linkedin_content_generator_setting.critic_prompt_path)
print(settings.settings.linkedin_content_generator_setting.reviser_prompt_path)


def read_prompt(file_path: str) -> str:
    with open(PROJECT_ROOT / file_path, "r", encoding="utf-8") as f:
        return f.read()


result = read_prompt(settings.settings.linkedin_content_generator_setting.writer_prompt_path)
print(result)
 
class ChkAgent:
    '''Minimal agent: a name, a system prompt, a way to produce a response.
    No inheritance tree, no pipeline — just enough to be reusable.'''

    def __init__(
            self, 
            name: str, 
            client, 
            model: str, 
            system_prompt: str):            

        print("=============CREATING ChkAgent==================")
        self.name = name
        self.client = client
        self.model = model
        self.system_prompt = system_prompt


    def run(self, input_text: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": input_text}],
        )
        return "".join(b.text for b in response.content if b.type == "text")



def make_subagent(client, model):
    ''' 3 subagents of class Agent of ChkAgent'''
    print("=============CREATING SUBAGENT==================")

    writer = ChkAgent(model= model, client= client,
        name="Writer", system_prompt= "You are a LinkedIn post writer. Write under 200 words.",
    )

    critic  = ChkAgent(model= model, client= client,
        name="critic", system_prompt= "You are a critic. Give exactly 5 numbered suggestions to improve the draft. Do not rewrite it.",
    )

    reviser = ChkAgent(model= model, client= client,
        name="reviser", system_prompt= "You are an editor. Rewrite the draft to address the critique. Output only the revised post.",
    )

    return writer, critic, reviser


def run_chain( topic: str)-> str:

    try:
        client = anthropic.Anthropic(
            base_url="http://localhost:11434",
            api_key="ollama",
            timeout=120,
            max_retries=2,
        )
    except Exception as e:
        print(f"error creating client {e}")

    writer, critic, reviser = make_subagent(client= client, model="gpt-oss:20b-cloud")

    print("=============IMPLEMENTING CHAIN==================")
    draft = writer.run(f"Write a LinkedIn post about: {topic}")
    critique = critic.run(f"Draft:\n{draft}\n\nTopic: {topic}")
    revised = reviser.run(f"Draft:\n{draft}\n\nCritique:\n{critique}")
    return {"draft": draft, "critique": critique, "revised": revised}

