import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging # Import logging
from google.generativeai import types # Added for media parts
import io # Added for byte stream handling

load_dotenv() # Load environment variables from .env file
logger = logging.getLogger(__name__) # Get a logger for this module

class GeminiFlashAPI:
    """
    A Python interface for Google's Gemini 1.5 Flash API.

    This class provides methods to configure the API client and send
    prompts to the Gemini model.

    Attributes:
        api_key (str): The API key for accessing Google's Generative AI services.
        model (genai.GenerativeModel): The configured Gemini model instance.
        model_name (str): The name of the model being used.
        system_instruction (str, optional): A system-level instruction for the model.
    """

    def __init__(self, api_key=None, model_name="gemini-2.0-flash", 
                 system_instruction="""You are an expert appliance repair assistant. Your primary goal is to help users diagnose and solve problems with their home appliances.

Follow these steps in your interaction:
1.  Ask for the appliance type, brand, model number, and a description of the specific problem.
2.  After getting this initial information, ask 1-2 essential clarifying questions (e.g., 'Is there power to the unit?', 'Are there any error codes displayed?').
3.  After you have asked a total of 2-3 questions and have a reasonable understanding of the issue, you must provide the comprehensive solution. Do not ask more questions.
4.  Structure your final solution response clearly with the following sections, using markdown for formatting:
    - **Summary:** A brief overview of the likely problem.
    - **Troubleshooting Walk-through:** A detailed, step-by-step guide to fixing the issue.
    - **Helpful Questions:** A list of additional questions the user can check to further diagnose the problem.
    - **Troubleshooting Flowchart:** A flowchart of the troubleshooting steps in Mermaid.js syntax. Enclose it in a markdown code block. Follow these strict rules for the flowchart:
      - Always wrap node text in double quotes (e.g., `A["Node text"]`). This is mandatory.
      - Use simple, unique IDs for nodes (e.g., `N1`, `N2`, `N3`).
      - Stick to basic `graph TD;` and `-->` syntax.
      - If a step involves replacing a part, add the recommended part number to the top of the node's text, using a line break. Example: `N4["Part #: 12345<br/>Replace heating element"]`.
      - **CRITICAL SYNTAX RULE: The text inside a node's double quotes MUST NOT contain any other double quotes. Replace any internal quotes with single quotes, or rephrase to avoid them entirely.**
      - Example:
        ```mermaid
        graph TD;
            A["Start"] --> B{"Check Power"};
            B -->|Yes| C{"Error Code?"};
            B -->|No| D["Check Outlet"];
        ```
    - **Part Recommendation:** If a part replacement is needed, identify the part and suggest a specific part number for the user's appliance model. Mention that availability and price may vary.

**Formatting Rules:**
- **Warnings:** Any text containing a "caution" or "warning" must be wrapped in `<span class="warning-text"></span>`. For example: `<span class="warning-text">Caution: Disconnect power before proceeding.</span>`
- **Part Numbers:** Any identified part number should be wrapped in `<span class="part-number"></span>`. For example: `<span class="part-number">WP3392519</span>`.

**Crucial Rule:** If a user's question or prompt is not related to diagnosing or repairing an appliance, you must respond by stating your purpose. For example, say: "My function is to assist with appliance repair. Please provide the information I requested about the appliance so I can help you." Do not answer off-topic questions.

Your tone should be helpful, clear, and professional. Keep your responses concise and easy to understand. Respond in all lowercase."""):
        """
        Initializes the GeminiFlashAPI client.

        Args:
            api_key (str, optional): The Google API key. If None or empty,
                                     it will try to fetch from the GOOGLE_API_KEY
                                     environment variable. Defaults to None.
            model_name (str, optional): The name of the Gemini model to use.
                                        Defaults to "gemini-2.0-flash".
            system_instruction (str, optional): A system-level instruction to guide the
                                                model's behavior. Defaults to a specific
                                                casual/romanticist tone.

        Raises:
            ValueError: If the API key is not provided (and not found in
                        environment variables if api_key arg is None/empty).
        """
        effective_api_key = api_key
        if not effective_api_key: # Checks for None or empty string
            logger.info("API_INTERFACE_LOG: API key not provided in __init__ arguments.")
            logger.info("API_INTERFACE_LOG: Attempting to load GOOGLE_API_KEY from environment variable...")
            effective_api_key = os.getenv("GOOGLE_API_KEY")
            if effective_api_key:
                logger.info("API_INTERFACE_LOG: Successfully loaded GOOGLE_API_KEY from environment.")
            else:
                logger.warning("API_INTERFACE_LOG: GOOGLE_API_KEY not found in environment variables.")
        else:
            logger.info(f"API_INTERFACE_LOG: Using API key provided directly as an argument (first 5 chars: {effective_api_key[:5]}...)." )

        if not effective_api_key:
            logger.error("API_INTERFACE_LOG: API key is MISSING. Cannot initialize Gemini client.")
            raise ValueError(
                "API_INTERFACE_ERROR: API key is missing. Please provide it directly, or set the GOOGLE_API_KEY "
                "environment variable (e.g., in a .env file)."
            )

        try:
            genai.configure(api_key=effective_api_key)
            logger.info("API_INTERFACE_LOG: genai.configure called successfully.")
            self.model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction
            )
            logger.info(f"API_INTERFACE_LOG: GenerativeModel '{model_name}' initialized.")
        except Exception as e:
            logger.error(f"API_INTERFACE_LOG: Error during genai.configure or GenerativeModel initialization: {e}", exc_info=True)
            raise # Re-raise the exception to be caught by app.py or calling code
            
        self.model_name = model_name
        self.api_key = effective_api_key # Store the actual key being used for reference
        self.system_instruction = system_instruction # Store for reference if needed
        logger.info(f"API_INTERFACE_LOG: GeminiFlashAPI initialized successfully with model: {self.model_name} (API Key: {self.api_key[:5]}...).")

    def generate_content(self, prompt, stream=False, generation_config=None, safety_settings=None):
        """
        Generates content based on the provided prompt.

        Args:
            prompt (str or list): The prompt to send to the model. Can be a simple
                                  string or a list of parts (e.g., for multimodal input).
            stream (bool, optional): If True, streams the response. Defaults to False.
            generation_config (genai.types.GenerationConfig, optional):
                                 Configuration for the generation process (e.g., temperature,
                                 max_output_tokens).
            safety_settings (list of genai.types.SafetySetting, optional):
                             Safety settings for the request.

        Returns:
            genai.types.GenerateContentResponse or iterator:
                If stream is False, returns the full response object.
                If stream is True, returns an iterator for streaming the response.

        Raises:
            Exception: If there's an error during API communication or generation.
        """
        try:
            if stream:
                response = self.model.generate_content(
                    prompt,
                    stream=True,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
            else:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
            return response
        except Exception as e:
            print(f"Error generating content: {e}")
            raise

    async def generate_content_async(self, prompt, generation_config=None, safety_settings=None):
        """
        Asynchronously generates content based on the provided prompt.

        Args:
            prompt (str or list): The prompt to send to the model.
            generation_config (genai.types.GenerationConfig, optional):
                                 Configuration for the generation process.
            safety_settings (list of genai.types.SafetySetting, optional):
                             Safety settings for the request.

        Returns:
            genai.types.GenerateContentResponse: The full response object.

        Raises:
            Exception: If there's an error during API communication or generation.
        """
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            return response
        except Exception as e:
            print(f"Error generating content asynchronously: {e}")
            raise

    def count_tokens(self, prompt):
        """
        Counts the number of tokens in the given prompt for the configured model.

        Args:
            prompt (str or list): The prompt content.

        Returns:
            genai.types.CountTokensResponse: An object containing the token count.

        Raises:
            Exception: If there's an error during token counting.
        """
        try:
            response = self.model.count_tokens(prompt)
            return response
        except Exception as e:
            print(f"Error counting tokens: {e}")
            raise

    async def count_tokens_async(self, prompt):
        """
        Asynchronously counts the number of tokens in the given prompt.

        Args:
            prompt (str or list): The prompt content.

        Returns:
            genai.types.CountTokensResponse: An object containing the token count.

        Raises:
            Exception: If there's an error during token counting.
        """
        try:
            response = await self.model.count_tokens_async(prompt)
            return response
        except Exception as e:
            print(f"Error counting tokens asynchronously: {e}")
            raise

    def start_chat_session(self, history=None):
        """
        Starts a new chat session with the configured model.

        Args:
            history (list of genai.types.Content, optional):
                     An optional list of previous messages to initialize the chat history.
                     Each item should be a dict like {"role": "user"/"model", "parts": ["text"]}.

        Returns:
            genai.ChatSession: A chat session object.
        
        Raises:
            Exception: If there's an error starting the chat.
        """
        logger.info(f"API_INTERFACE_LOG: Starting a new chat session with model {self.model_name}.")
        try:
            # Convert history to google.generativeai.types.Content objects if necessary
            # For simplicity, assuming history is already in the correct format or None
            # For a robust implementation, you might add conversion logic here.
            chat_session = self.model.start_chat(history=history or [])
            logger.info(f"API_INTERFACE_LOG: Chat session started. Initial history length: {len(chat_session.history)}")
            return chat_session
        except Exception as e:
            logger.error(f"API_INTERFACE_LOG: Error starting chat session: {e}", exc_info=True)
            raise

    def send_chat_message(self, chat_session, message_text, stream=False, media_bytes=None, media_mime_type=None):
        """
        Sends a message to an existing chat session and gets the model's response.

        Args:
            chat_session (genai.ChatSession): The active chat session object.
            message_text (str): The user's message.
            stream (bool, optional): If True, streams the response. Defaults to False.
            media_bytes (bytes, optional): The bytes of the image or video file.
            media_mime_type (str, optional): The MIME type of the media_bytes (e.g., "image/jpeg", "video/mp4").

        Returns:
            genai.types.GenerateContentResponse or iterator:
                If stream is False, returns the full response object.
                If stream is True, returns an iterator for streaming the response.
        
        Raises:
            Exception: If there's an error sending the message or getting the response.
            ValueError: If chat_session is not valid or media is provided incorrectly.
        """
        logger.info(f"API_INTERFACE_LOG: Preparing to send message to chat session. Text: '{message_text[:50]}...', Media present: {media_bytes is not None}")
        if not chat_session:
            logger.error("API_INTERFACE_LOG: Chat session is not valid (e.g., None).")
            raise ValueError("Chat session is not valid.")

        prompt_parts = []
        if media_bytes and media_mime_type:
            if media_mime_type.startswith("image/") or media_mime_type.startswith("video/"):
                # Construct the media part as a dictionary
                prompt_parts.append({
                    "inline_data": {
                        "mime_type": media_mime_type,
                        "data": media_bytes
                    }
                })
                logger.info(f"API_INTERFACE_LOG: Added media part with MIME type: {media_mime_type}")
            else:
                logger.warning(f"API_INTERFACE_LOG: Unsupported media_mime_type for direct Part creation: {media_mime_type}. Media will not be sent.")
        
        # Always add the text part if message_text is present
        if message_text:
            prompt_parts.append({"text": message_text})
        elif not prompt_parts: # If no media and no text, it's an issue
            logger.error("API_INTERFACE_LOG: Cannot send an empty message (no text and no media).")
            raise ValueError("Cannot send an empty message (no text and no media).")


        try:
            if not prompt_parts: # Should be caught above, but as a safeguard
                 logger.error("API_INTERFACE_LOG: No parts to send in the message.")
                 raise ValueError("Message content is empty.")

            logger.info(f"API_INTERFACE_LOG: Sending {len(prompt_parts)} parts to chat session. First part type: {type(prompt_parts[0]) if prompt_parts else 'N/A'}")
            response = chat_session.send_message(prompt_parts, stream=stream)
            # The chat_session.history is automatically updated by the send_message call.
            logger.info(f"API_INTERFACE_LOG: Message sent and response received. Chat history length: {len(chat_session.history)}")
            return response
        except Exception as e:
            logger.error(f"API_INTERFACE_LOG: Error sending chat message: {e}", exc_info=True)
            raise

# Example Usage (Illustrative - requires GOOGLE_API_KEY to be set)
if __name__ == "__main__":
    # Ensure you have GOOGLE_API_KEY set in your environment variables
    # e.g., export GOOGLE_API_KEY="YOUR_API_KEY"

    try:
        # Initialize the API
        gemini_client = GeminiFlashAPI()

        # --- Simple text generation ---
        print("\n--- Simple Text Generation ---")
        prompt_text = "Explain the concept of a Large Language Model in simple terms."
        response = gemini_client.generate_content(prompt_text)
        if response.parts:
            print("Generated Text:")
            print(response.text)
        else:
            print("No content generated or response blocked.")
            if response.prompt_feedback:
                print(f"Prompt Feedback: {response.prompt_feedback}")


        # --- Token Counting ---
        print("\n--- Token Counting ---")
        token_count_response = gemini_client.count_tokens(prompt_text)
        print(f"Token count for '{prompt_text[:30]}...': {token_count_response.total_tokens}")


        # --- Streaming response ---
        print("\n--- Streaming Text Generation ---")
        stream_prompt = "Write a short story about a friendly robot discovering music."
        stream_response = gemini_client.generate_content(stream_prompt, stream=True)
        print("Streaming Generated Text:")
        for chunk in stream_response:
            if chunk.parts:
                print(chunk.text, end="")
            else:
                print(f"\nStream chunk blocked or empty. Feedback: {chunk.prompt_feedback if chunk.prompt_feedback else 'N/A'}")
        print("\n--- End of Stream ---")


        # --- Chat example ---
        print("\n--- Chat Session Example (Updated) ---")
        if client_for_async: # Reuse a successfully initialized client
            try:
                chat_session_example = client_for_async.start_chat_session()
                print(f"Chat session started with model: {client_for_async.model_name}")

                user_message1 = "Hi Gemini, can you tell me a fun fact about space?"
                print(f"User: {user_message1}")
                chat_response1 = client_for_async.send_chat_message(chat_session_example, user_message1)
                if chat_response1.parts:
                    print(f"Gemini: {chat_response1.text}")
                else:
                    feedback_msg = str(chat_response1.prompt_feedback) if chat_response1.prompt_feedback else "N/A"
                    print(f"Gemini: Response blocked or empty. Feedback: {feedback_msg}")

                user_message2 = "That's interesting! What's another one?"
                print(f"User: {user_message2}")
                chat_response2 = client_for_async.send_chat_message(chat_session_example, user_message2)
                if chat_response2.parts:
                    print(f"Gemini: {chat_response2.text}")
                else:
                    feedback_msg = str(chat_response2.prompt_feedback) if chat_response2.prompt_feedback else "N/A"
                    print(f"Gemini: Response blocked or empty. Feedback: {feedback_msg}")

                print("\nFinal Chat History:")
                for message in chat_session_example.history:
                    role = "User" if message.role == "user" else "Model"
                    text_content = message.parts[0].text if message.parts else "[empty part]"
                    print(f"  {role}: {text_content}")
            except Exception as e:
                print(f"Error in chat example: {e}")
        else:
            print("Skipping chat example as no client was initialized successfully.")


        # --- Asynchronous example (requires an event loop) ---
        import asyncio

        async def run_async_examples(client_instance): # Pass client instance
            print("\n--- Asynchronous Text Generation ---")
            async_prompt = "What are the key features of Python 3.12?"
            async_response = await client_instance.generate_content_async(async_prompt)
            if async_response.parts:
                print("Async Generated Text:")
                print(async_response.text)
            else:
                print("Async: No content generated or response blocked.")
                if async_response.prompt_feedback:
                    print(f"Async Prompt Feedback: {async_response.prompt_feedback}")


            print("\n--- Asynchronous Token Counting ---")
            async_token_count_response = await client_instance.count_tokens_async(async_prompt)
            print(f"Async Token count for '{async_prompt[:30]}...': {async_token_count_response.total_tokens}")

        # To run async examples:
        # asyncio.run(run_async_examples(gemini_client)) # Pass the client
        # Note: If running in Jupyter or an environment with an existing event loop,
        # use `await run_async_examples(gemini_client)` instead of `asyncio.run()`.
        # For simplicity in this script, we'll call it directly if possible,
        # but be mindful of event loop management in different environments.
        
        # Modify the example usage to pass the client to async functions
        # And ensure client is initialized before calling.
        client_for_async = None
        if 'gemini_client' in locals() and gemini_client.api_key: # Check if original example client is there
            client_for_async = gemini_client
        elif 'gemini_client' in locals() and gemini_client.api_key: # Fallback to env test client
            client_for_async = gemini_client

        if client_for_async:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    print("\nAsync examples can be run by awaiting `run_async_examples(client_instance)` in an async context.")
                else: 
                     asyncio.run(run_async_examples(client_for_async))
            except RuntimeError: 
                asyncio.run(run_async_examples(client_for_async))
        else:
            print("\nSkipping async examples as no client initialized successfully for them.")


    except ValueError as ve:
        print(f"Configuration Error: {ve}")
        print("Please ensure your GOOGLE_API_KEY environment variable is set correctly.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# End Generation Here
