import os
import logging
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.agents import Tool, initialize_agent, AgentType
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
        """
        self.llm_model = llm_model
        self.temperature = temperature
        self.llm = self._initialize_llm()
        self.tools = []  # list of Tool objects
        self.chain = None
        self._setup_base_chain()
    
    def _initialize_llm(self):
        """Initialize the LLM based on the model type."""
        try:
            if self.llm_model == "openai":
                # ---------- OpenAI ----------
                try:
                    from langchain_openai import OpenAI
                    return OpenAI(temperature=self.temperature)
                except ImportError:
                    # Fallback if langchain_openai not installed
                    from langchain_community.llms import OpenAI
                    return OpenAI(temperature=self.temperature)
            elif self.llm_model == "claude":
                # ---------- Claude (Anthropic) ----------
                try:
                    # LangChain fournit un wrapper chat pour les modèles Claude
                    from langchain_anthropic import ChatAnthropic
                    return ChatAnthropic(
                        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                        model_name="claude-3-sonnet-20240229",  # you can change the model
                        temperature=self.temperature,
                    )
                except ImportError:
                    # If the package is not installed, we return None → fallback deterministic
                    return None
            elif self.llm_model.startswith("hf:"):
                # ---------- HuggingFace Hub ----------
                from langchain_community.llms import HuggingFaceHub
                model_name = self.llm_model[3:]  # Remove "hf:" prefix
                return HuggingFaceHub(
                    repo_id=model_name,
                    model_kwargs={"temperature": self.temperature, "max_length": 512},
                )
            elif self.llm_model == "azure":
                # ---------- Azure OpenAI / AI Foundry ----------
                try:
                    from langchain_openai import AzureChatOpenAI
                    return AzureChatOpenAI(
                        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15"),
                        temperature=self.temperature,
                    )
                except ImportError:
                    from langchain_openai import AzureOpenAI
                    return AzureOpenAI(
                        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15"),
                        temperature=self.temperature,
                    )
            elif self.llm_model == "local":
                # For local LLMs, we'll need a specific implementation
                # For now, return None to trigger deterministic fallback
                return None
            else:
                # Default to OpenAI if not specified
                try:
                    from langchain_openai import OpenAI
                    return OpenAI(temperature=self.temperature)
                except ImportError:
                    from langchain_community.llms import OpenAI
                    return OpenAI(temperature=self.temperature)
        except Exception as err:
            # If any error occurs during LLM initialization, fall back to deterministic
            # This includes missing API key, invalid model name, etc.
            logger.warning("Falling back to deterministic kickstart initialization: %s", err)
            return None
    
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
    
    def add_tool(self, name: str, func: callable, description: str):
        """Add a LangChain tool to the service."""
        tool = Tool(name=name, func=func, description=description)
        self.tools.append(tool)
    
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
                    "Falling back to LangChain kickstart implementation: %s",
                    err,
                )
        
        # Use LangChain-based generation
        if self.llm is None:
            # Deterministic fallback for local/no LLM case
            impacted_department = context.get("impacted_department", "l'équipe concernée")
            problem_statement = (
                f'Le processus "{context.get("target_process", "N/A")}" '
                f"crée une friction majeure ({context.get('current_friction', 'N/A')}) "
                f"pour {impacted_department}."
            )
            proposed_solution = "Mettre en place un assistant IA supervisé orienté qualification, recommandation et validation humaine obligatoire."
            justification = "Réponse déterministe générée en l'absence de modèle LLM configuré."
            return {
                "problem_statement": problem_statement,
                "proposed_solution": proposed_solution,
                "justification": justification
            }
        
        # If we have tools, try to use an agent that can call them
        if self.tools:
            try:
                agent = initialize_agent(
                    self.tools,
                    self.llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=False,
                    handle_parsing_errors=True,
                )
                result = agent.run(context)
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
            except Exception as err:
                logger.warning("Kickstart tool-agent fallback triggered: %s", err)
        
        # Use LangChain-based generation (chain)
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
        except Exception as err:
            # Final fallback
            problem_statement = f"Erreur lors de la génération : {err}"
            proposed_solution = "Veuillez vérifier la configuration du modèle LLM."
            justification = "Erreur technique lors de l'appel au modèle LLM."
            return {
                "problem_statement": problem_statement,
                "proposed_solution": proposed_solution,
                "justification": justification
            }