import cmd 
import sys
import os

# Ensure the core and modules directories are accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'core')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'modules')))

from core.llm_client import generate_response

class OpenOsintManager:
    """Handles the business logic for OpenOSINT operations."""
    
    def greet_user(self, name: str = "") -> str:
        return f"Hello {name}!" if name else "Hello!"

class OpenOsintShell(cmd.Cmd):
    """CLI Controller for the OpenOSINT interface."""
    
    intro = "Welcome to OpenOSINT. Type 'help' or '?' to list commands.\n"
    prompt = "(openosint): "
    
    def __init__(self):
        super().__init__()
        self.manager = OpenOsintManager()
        # Initialize conversation memory
        self.history = []

    def default(self, line: str):
        """
        Triggered when input doesn't match any 'do_' command.
        Sends the text to the AI with context preservation.
        """
        if line.strip():
            # Get response from AI passing the current history
            response = generate_response(line, history=self.history)
            
            # Update history with the new exchange
            self.history.append({'role': 'user', 'content': line})
            self.history.append({'role': 'assistant', 'content': response})
            
            print(response)
        else:
            super().default(line)

    def do_run_ai(self, arg: str):
        """Force an AI response using the current context. Usage: run_ai [prompt]"""
        if arg:
            self.default(arg)
        else:
            print("*** Error: please provide a prompt.")
            
    def do_clear(self, _arg: str):
        """Clear the conversation memory. Usage: clear"""
        self.history = []
        print("--- Conversation memory cleared ---")
    
    def do_greet(self, arg: str):
        """Greet a user by name. Usage: greet [name]"""
        response = self.manager.greet_user(arg)
        print(response)
    
    def do_exit(self, _arg: str) -> bool:
        """Exit the application."""
        print("Goodbye")
        return True
    
    def do_EOF(self, line):
        """Exit with Ctrl+D"""
        return self.do_exit(line)
        
    def emptyline(self):
        """Override to prevent repeating the last command on empty input."""
        pass

def main():
    """Entry point of the script."""
    shell = OpenOsintShell()
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
        
if __name__ == "__main__":
    main()