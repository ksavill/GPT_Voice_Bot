import os
import time
import requests
from typing import Dict, Callable, Any, Optional, Tuple
import json
import re

class OpenAIHandler:
    def __init__(self, api_key=None, model="gpt-3.5-turbo", max_history=10, max_tokens=300, temperature=0.5, retries=3, timeout=10):
        self.api_key = api_key or os.environ.get("openai_token")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set the 'openai_token' environment variable.")
        self.model = model
        self.max_history = max_history
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.retries = retries
        self.timeout = timeout
        self.conversation_history = []
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Define available functions
        self.functions = [
            {
                "name": "CreateTicket",
                "description": "Creates a support ticket with the provided user details and issue description.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the user."
                        },
                        "email": {
                            "type": "string",
                            "description": "The user's email address."
                        },
                        "issue": {
                            "type": "string",
                            "description": "Description of the issue."
                        },
                        "contact_number": {
                            "type": "string",
                            "description": "The user's contact number (optional)."
                        }
                    },
                    "required": ["name", "email", "issue"]
                }
            }
        ]
        
        # Map function names to actual Python functions
        self.function_map: Dict[str, Callable[..., Any]] = {
            "CreateTicket": CreateTicket
        }
        
        # To keep track of incomplete function calls
        self.pending_function_calls: Dict[str, Dict[str, Any]] = {}
        
        # To keep track of confirmation steps
        self.confirmation_steps: Dict[str, Dict[str, Any]] = {}
        
    def generate_response(self, prompt: str) -> Tuple[str, bool]:
        # Add user input to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        self.trim_conversation_history()

        # Handle pending confirmations first
        if self.confirmation_steps:
            for func_name, confirm_info in list(self.confirmation_steps.items()):
                if confirm_info.get("awaiting_confirmation"):
                    user_response = prompt.strip().lower()
                    current_email = confirm_info.get("email_being_confirmed", "")
                    
                    # Extract email and additional info from the user response
                    new_email, additional_info = self.extract_email_and_additional_info(user_response)
                    
                    if new_email and new_email != current_email:
                        # User provided a new email, update the args
                        confirm_info["args"]["email"] = new_email
                        confirm_info["email_being_confirmed"] = new_email
                        # Optionally, handle additional_info if needed
                        if additional_info and "contact_number" in additional_info:
                            confirm_info["args"]["contact_number"] = additional_info["contact_number"]
                        
                        prompt_confirm = f"You provided a new email: **{new_email}**. Is this correct? (yes/no)"
                        self.conversation_history.append({"role": "assistant", "content": prompt_confirm})
                        return prompt_confirm, False
                    else:
                        # Interpret the response as confirmation or denial
                        is_confirmed = self.interpret_confirmation(user_response)
                        if is_confirmed is True:
                            # Proceed with ticket creation using the confirmed email
                            function_args = confirm_info["args"]
                            function = self.function_map.get(func_name)
                            if function:
                                try:
                                    function_response = function(**function_args)
                                    ticket_id = function_response.get("ticket_id")
                                    if ticket_id:
                                        assistant_message = f"Ticket created successfully with ID: {ticket_id}. Is there anything else I can help with?"
                                    else:
                                        assistant_message = f"I was unable to create the ticket due to {function_response.get('error', 'an error')}. Please provide the information again."
                                    self.conversation_history.append({"role": "assistant", "content": assistant_message})
                                    # Reset states after successful creation
                                    self.reset_conversation()
                                    finished = self._check_conversation_finished()
                                    return assistant_message, finished
                                except Exception as e:
                                    error_message = f"An error occurred while creating the ticket: {e}"
                                    self.conversation_history.append({"role": "assistant", "content": error_message})
                                    return error_message, False
                            else:
                                error_message = f"Function '{func_name}' is not implemented."
                                self.conversation_history.append({"role": "assistant", "content": error_message})
                                return error_message, False
                        elif is_confirmed is False:
                            # User said "no", so prompt for a new email
                            prompt_retry = "It seems like the email is incorrect. Please provide a new email address."
                            self.conversation_history.append({"role": "assistant", "content": prompt_retry})
                            # Reset confirmation step to expect a new email
                            self.confirmation_steps[func_name]["awaiting_confirmation"] = False
                            self.pending_function_calls[func_name] = confirm_info
                            return prompt_retry, False
                        else:
                            # Unable to interpret, prompt again
                            prompt_retry = f"Please confirm if the email **{current_email}** is correct or provide a new email."
                            self.conversation_history.append({"role": "assistant", "content": prompt_retry})
                            return prompt_retry, False

        # If there is a pending function call, handle missing fields
        if self.pending_function_calls:
            function_name, pending_info = next(iter(self.pending_function_calls.items()))
            missing_fields = pending_info.get("missing_fields", [])
            if missing_fields:
                # Prompt the user for the first missing field
                next_field = missing_fields[0]
                field_description = self.get_field_description(function_name, next_field)
                prompt_missing = f"Please provide the following information to proceed:\n- {field_description}"
                self.conversation_history.append({"role": "assistant", "content": prompt_missing})
                return prompt_missing, False

        # Prepare data with function definitions for GPT-3
        data = {
            "model": self.model,
            "messages": self.conversation_history,
            "max_tokens": self.max_tokens,
            "n": 1,
            "stop": None,
            "temperature": self.temperature,
            "functions": self.functions,  # Include function definitions
            "function_call": "auto"  # Let the model decide when to call a function
        }

        response_json = self._make_gpt_request(data)

        if not response_json:
            raise ValueError("No response generated.")

        message = response_json.get("choices")[0].get("message")
        
        if message.get("function_call"):
            # Extract function name and arguments
            function_name = message["function_call"]["name"]
            function_args = json.loads(message["function_call"].get("arguments", "{}"))
            
            # Validate required fields
            function_definition = next((f for f in self.functions if f["name"] == function_name), None)
            if function_definition:
                required_fields = function_definition["parameters"].get("required", [])
                missing_fields = [field for field in required_fields if field not in function_args or not function_args[field]]
                
                if missing_fields:
                    # Store the pending function call with missing fields
                    self.pending_function_calls[function_name] = {
                        "args": function_args,
                        "missing_fields": missing_fields
                    }
                    # Prompt the user to provide missing information
                    missing = ', '.join(missing_fields)
                    prompt_missing = f"To create a ticket, I need the following information: {missing}. Please provide them."
                    self.conversation_history.append({"role": "assistant", "content": prompt_missing})
                    return prompt_missing, False
                else:
                    # All required fields are present, but check if email needs confirmation
                    email = function_args.get("email", "")
                    if self.is_valid_email(email):
                        # Ask for confirmation of the email
                        prompt_confirm = f"Please confirm if the email **{email}** is correct or provide a new email."
                        self.conversation_history.append({"role": "assistant", "content": prompt_confirm})
                        # Set confirmation state
                        self.confirmation_steps[function_name] = {
                            "args": function_args,
                            "awaiting_confirmation": True,
                            "email_being_confirmed": email
                        }
                        return prompt_confirm, False
                    else:
                        # Invalid email format, prompt user to re-enter
                        prompt_invalid = f"The email address **{email}** seems invalid. Please provide a valid email address."
                        self.conversation_history.append({"role": "assistant", "content": prompt_invalid})
                        # Update pending function call to require email again
                        self.pending_function_calls[function_name]["missing_fields"].append("email")
                        return prompt_invalid, False
            else:
                error_message = f"Function definition for '{function_name}' not found."
                self.conversation_history.append({"role": "assistant", "content": error_message})
                return error_message, False
        else:
            # Regular response from GPT
            response_text = message.get("content", "")
            self.conversation_history.append({"role": "assistant", "content": response_text})
            finished = self._check_conversation_finished()
            return response_text, finished

    def interpret_confirmation(self, user_response: str) -> Optional[bool]:
        """
        Interpret the user's response as confirmation, denial, or unclear.
        
        Returns:
            True if confirmed,
            False if denied,
            None if unclear.
        """
        affirmative_keywords = ["yes", "yep", "correct", "right", "sure", "affirmative", "indeed", "that’s correct", "exactly"]
        negative_keywords = ["no", "nope", "incorrect", "wrong", "not", "negative", "that's not correct", "not right", "different email"]

        # Check for affirmative
        if any(word in user_response for word in affirmative_keywords):
            return True
        # Check for negative
        if any(word in user_response for word in negative_keywords):
            return False
        # Unable to determine
        return None

    def _make_gpt_request(self, data: dict) -> Optional[dict]:
        """Helper method to make a GPT request and return the response JSON."""
        for attempt in range(self.retries):
            try:
                response = self.session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=self.headers,
                    json=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                response_json = response.json()
                return response_json
            except (requests.exceptions.RequestException, ValueError) as e:
                if attempt < self.retries - 1:
                    sleep_time = 2 ** attempt
                    print(f"Error: {e}. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    raise Exception(f"Failed after {self.retries} attempts: {e}")
        return None

    def _check_conversation_finished(self) -> bool:
        """Helper method to check if the conversation is concluded."""
        finish_prompt = "Is this conversation complete? Answer with 'yes' or 'no'."
        check_data = {
            "model": self.model,
            "messages": self.conversation_history + [{"role": "user", "content": finish_prompt}],
            "max_tokens": 10,
            "n": 1,
            "temperature": 0.0,
            "functions": self.functions,
            "function_call": "none"
        }

        response_json = self._make_gpt_request(check_data)
        if not response_json:
            return False

        message = response_json.get("choices")[0].get("message", {})
        response_text = message.get("content", "").strip().lower()
        if response_text in ["yes", "yes."]:
            return True
        return False

    def trim_conversation_history(self) -> None:
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def reset_conversation(self) -> None:
        self.conversation_history = []
        self.pending_function_calls = {}
        self.confirmation_steps = {}

    def handle_user_input(self, user_input: str) -> Tuple[str, bool]:
        """
        Process user input and generate a response.

        This method can be used as an interface to interact with the OpenAIHandler.
        """
        return self.generate_response(user_input)

    def get_field_description(self, function_name: str, field_name: str) -> str:
        """Retrieve the description of a specific field from the function definition."""
        function_definition = next((f for f in self.functions if f["name"] == function_name), None)
        if function_definition:
            properties = function_definition["parameters"].get("properties", {})
            field = properties.get(field_name, {})
            description = field.get("description", field_name)
            return f"{field_name.replace('_', ' ').capitalize()}: {description}"
        return field_name

    def is_valid_email(self, email: str) -> bool:
        """Enhanced regex-based email validation to handle variations like 'at' or 'that'."""
        # Normalize common variations
        email_normalized = re.sub(r'\bat\b|\bthat\b', '@', email, flags=re.IGNORECASE)
        email_normalized = re.sub(r'\s+', '', email_normalized)  # Remove any whitespace
        # Simple regex to validate email
        regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        return re.match(regex, email_normalized) is not None

    def extract_email_and_additional_info(self, user_response: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Extract email and other information from the user's response.

        Returns a tuple of (new_email, additional_info_dict)
        """
        # Normalize common variations
        response_normalized = re.sub(r'\bat\b|\bthat\b', '@', user_response, flags=re.IGNORECASE)
        response_normalized = re.sub(r'\s+', '', response_normalized)  # Remove any whitespace

        # Regex to find email addresses
        email_regex = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
        emails = re.findall(email_regex, response_normalized)
        new_email = emails[-1] if emails else None

        # Extract contact number if present (simple pattern)
        phone_regex = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_regex, user_response)
        contact_number = phones[-1] if phones else None

        additional_info = {}
        if contact_number:
            additional_info['contact_number'] = contact_number

        return new_email, additional_info if additional_info else None

def CreateTicket(name: str, email: str, issue: str, contact_number: str = None) -> Dict[str, Any]:
    """
    Creates a support ticket with the provided details.

    Parameters:
        name (str): The name of the user.
        email (str): The user's email address.
        issue (str): Description of the issue.
        contact_number (str, optional): The user's contact number.

    Returns:
        dict: A dictionary containing ticket details or an error message.
    """
    # Validate the email format
    if not OpenAIHandler().is_valid_email(email):
        return {"error": "Invalid email format"}

    # Simulate ticket creation process (integrate with a real ticketing system)
    try:
        ticket = {
            "ticket_id": "12345",
            "name": name,
            "email": email,
            "issue": issue,
            "contact_number": contact_number,
            "status": "Open",
            "created_at": "2024-04-01T12:34:56Z"
        }
        print(f"Ticket Created: {ticket}")
        return ticket
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return {"error": "Failed to make ticket"}