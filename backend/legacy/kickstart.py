from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
# Try to import from existing llm_kickstart if available, else use fallback
try:
    from ai_value_studio.llm_kickstart import LLMBasedKickstartService
    HAS_EXISTING_KICKSTART = True
except ImportError:
    HAS_EXISTING_KICKSTART = False
    from langchain_community.llms import OpenAI  # Placeholder; user will configure

class KickstartService:
    def __init__(self):
        if HAS_EXISTING_KICKSTART:
            self.service = LLMBasedKickstartService()
        else:
            # Fallback to basic OpenAI (user must set OPENAI_API_KEY)
            self.llm = OpenAI(temperature=0.7)
            self.prompt = PromptTemplate(
                input_variables=["organization", "target_process", "current_friction", "impacted_department"],
                template="En tant qu'expert en cadrage IA, analyse ce contexte :\n- Organisation : {organization}\n- Processus cible : {target_process}\n- Friction principale : {current_friction}\n- Département impacté : {impacted_department}\n\nGénère :\n1. Un problem statement clair et mesurable\n2. Une solution IA proposée (avec niveau d'autonomie recommandé : Assist/Recommend/Execute with approval/Autonomous)\n3. Une justification courte\n\nRéponds en JSON avec les clés : problem_statement, proposed_solution, justification"
            )
            self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def generate_kickstart(self, context: dict) -> dict:
        if HAS_EXISTING_KICKSTART:
            # Assuming existing service has a generate method
            return self.service.generate_kickstart(context)
        else:
            result = self.chain.run(context)
            # In practice, parse JSON safely; here we assume well-formed output for simplicity
            import json
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # Fallback if output isn't pure JSON
                return {
                    "problem_statement": result.strip(),
                    "proposed_solution": "Solution IA à déterminer",
                    "justification": "Génération IA brute - à affiner"
                }