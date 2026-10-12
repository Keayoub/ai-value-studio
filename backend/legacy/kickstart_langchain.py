import logging

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
# Try to import from existing llm_kickstart if available, else use LangChain directly
try:
    from ai_value_studio.llm_kickstart import LLMBasedKickstartService
    HAS_EXISTING_KICKSTART = True
except ImportError:
    HAS_EXISTING_KICKSTART = False

logger = logging.getLogger(__name__)

class KickstartService:
    def __init__(self, llm_model="openai", temperature=0.7):
        """
        Initialize the kickstart service with LangChain for extensibility.
        
        Args:
            llm_model: "openai" for OpenAI models, or a HuggingFace model ID, or "local" for local LLMs
            temperature: Sampling temperature for generation
        """
        self.llm_model = llm_model
        self.temperature = temperature
        self.llm = self._initialize_llm()
        self.chain = None
        self._setup_base_chain()
        
    def _initialize_llm(self):
        """Initialize the LLM based on the model type."""
        if self.llm_model == "openai":
            try:
                from langchain_openai import OpenAI
                return OpenAI(temperature=self.temperature)
            except ImportError:
                # Fallback if langchain_openai not installed
                from langchain_community.llms import OpenAI
                return OpenAI(temperature=self.temperature)
        elif self.llm_model.startswith("hf:"):
            # HuggingFace model: format "hf:model_name"
            from langchain_community.llms import HuggingFaceHub
            model_name = self.llm_model[3:]  # Remove "hf:" prefix
            return HuggingFaceHub(
                repo_id=model_name,
                model_kwargs={"temperature": self.temperature, "max_length": 512}
            )
        elif self.llm_model == "local":
            # Placeholder for local LLMs (would need specific implementation)
            # For now, fall back to a simple deterministic response
            return None
        else:
            # Default to OpenAI if not specified
            try:
                from langchain_openai import OpenAI
                return OpenAI(temperature=self.temperature)
            except ImportError:
                from langchain_community.llms import OpenAI
                return OpenAI(temperature=self.temperature)
    
    def _setup_base_chain(self):
        """Set up the base LLM chain for kickstart generation."""
        if self.llm is None:
            # Local LLM fallback - will use deterministic responses
            self.chain = None
            return
            
        self.prompt = PromptTemplate(
            input_variables=["organization", "target_process", "current_friction", "impacted_department"],
            template="""En tant qu'expert en cadrage IA, analyse ce contexte :
- Organisation : {organization}
- Processus cible : {target_process}
- Friction principale : {current_friction}
- Département impacté : {impacted_department}

Génère :
1. Un problem statement clair et mesurable
2. Une solution IA proposée (avec niveau d'autonomie recommandé : Assist/Recommend/Execute with approval/Autonomous)
3. Une justification courte

Réponds en JSON avec les clés : problem_statement, proposed_solution, justification"""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def generate_kickstart(self, context: dict) -> dict:
        """
        Generate kickstart content using LangChain.
        
        Args:
            context: Dictionary containing organization, target_process, current_friction, impacted_department
            
        Returns:
            Dictionary with problem_statement, proposed_solution, justification
        """
        # If we have an existing kickstart service, use it first
        if HAS_EXISTING_KICKSTART:
            try:
                service = LLMBasedKickstartService()
                return service.generate_kickstart(context)
            except Exception as err:
                logger.warning(
                    "Falling back to legacy LangChain kickstart implementation: %s",
                    err,
                )
        
        # Use LangChain-based generation
        if self.llm is None:
            # Deterministic fallback for local/no LLM case
            target_process = context.get("target_process", "N/A")
            current_friction = context.get("current_friction", "N/A")
            impacted_department = context.get(
                "impacted_department",
                "l'équipe concernée",
            )
            return {
                "problem_statement": (
                    f'Le processus "{target_process}" crée une friction majeure '
                    f"({current_friction}) pour {impacted_department}."
                ),
                "proposed_solution": "Mettre en place un assistant IA supervisé orienté qualification, recommandation et validation humaine obligatoire.",
                "justification": "Réponse déterministe générée en l'absence de modèle LLM configuré.",
            }
        
        try:
            result = self.chain.run(context)
            # Try to parse as JSON first
            import json
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # If not JSON, return the raw text as problem statement
                return {
                    "problem_statement": result.strip(),
                    "proposed_solution": "Solution IA proposée (voir texte complet)",
                    "justification": "Justification à extraire de la réponse complète"
                }
        except Exception as e:
            # Final fallback
            return {
                "problem_statement": f"Erreur lors de la génération : {str(e)}",
                "proposed_solution": "Veuillez vérifier la configuration du modèle LLM.",
                "justification": "Erreur technique lors de l'appel au modèle LLM."
            }