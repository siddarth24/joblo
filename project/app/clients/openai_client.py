import logging
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", temperature: float = 0.7, max_tokens: int = 3000, top_p: float = 1.0):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        
        try:
            self._llm = ChatOpenAI(
                openai_api_key=self.api_key,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                model_kwargs={"top_p": self.top_p}
            )
            # It's good practice to define the chain structure once if it's static
            prompt_template = PromptTemplate(
                input_variables=["prompt"], # This matches how core_generate_resume uses it
                template="{prompt}"
            )
            self._chain = LLMChain(llm=self._llm, prompt=prompt_template)
            logger.info(f"OpenAIClient initialized successfully for model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpenAI or LLMChain in OpenAIClient: {e}", exc_info=True)
            raise ConnectionError(f"OpenAIClient initialization failed: {e}")

    def generate_text(self, prompt_text: str) -> str:
        """
        Generates text using the configured LLM.
        """
        if not self._chain:
            logger.error("OpenAIClient's LLM chain is not initialized. Cannot generate text.")
            raise RuntimeError("LLM chain not initialized. OpenAIClient may have failed during construction.")
            
        try:
            logger.debug(f"OpenAIClient generating text for prompt (first 50 chars): {prompt_text[:50]}...")
            generated_content = self._chain.run({"prompt": prompt_text})
            logger.info(f"OpenAIClient successfully generated text (length: {len(generated_content)}).")
            return generated_content
        except Exception as e:
            logger.error(f"Error during text generation with OpenAIClient: {e}", exc_info=True)
            # It's important to raise an error that reflects the generate_resume function's exceptions
            raise ConnectionError(f"Error communicating with OpenAI API via OpenAIClient: {e}") 