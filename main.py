import cmd 
import sys
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

    def default(self, line: str):
        """
        Viene chiamato quando l'input non corrisponde a nessun metodo 'do_'.
        Invia il testo direttamente all'IA.
        """
        if line.strip():
            print(generate_response(line))
        else:
            super().default(line)

    def do_run_ai(self, arg: str):
        """Force an AI response. Usage: run_ai [prompt]"""
        if arg:
            print(generate_response(arg))
        else:
            print("*** Error: please provide a prompt.")
    
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