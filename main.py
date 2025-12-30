import os
from dotenv import load_dotenv
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools
from src.personal_assistant.chroma_memory import ChromaMemoryTools
from src.personal_assistant.arango_memory import ArangoMemoryTools

def main():
    """
    Main function to run a demonstration of the personal assistant agent.
    """
    # Load env from .env.local (preferred) and .env without relying on auto-discovery
    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)

    # Initialize the tools
    memory = None
    if os.getenv("ARANGO_URL"):
        try:
            memory = ArangoMemoryTools()
            print(f"Using ArangoDB memory at {os.getenv('ARANGO_URL')} db={os.getenv('ARANGO_DB', 'agent_memory')}")
        except Exception as e:
            print(f"Arango unavailable, trying ChromaDB (error: {e})")
    if memory is None:
        try:
            memory = ChromaMemoryTools()
            print("Using ChromaDB-backed memory at ./.chroma")
        except Exception as e:
            print(f"Falling back to in-memory mock memory (Chroma unavailable: {e})")
            memory = MockMemoryTools()
    calendar = MockCalendarTools()
    tasks = MockTaskTools()

    # Initialize the agent
    agent = PersonalAssistantAgent(memory, calendar, tasks)

    # Simulate a user request
    user_request = "remind me to buy milk"
    print(f"Executing user request: '{user_request}'")

    # Execute the request
    result = agent.execute_request(user_request)

    # Print the results
    print("\n--- Agent Execution Summary ---")
    print(f"Plan: {result['plan']}")
    print(f"Execution Results: {result['execution_results']}")
    print("\n--- State After Execution ---")
    print(f"Tasks: {tasks.tasks}")
    mem_nodes = getattr(memory, "nodes", "external store")
    print(f"Memory Nodes: {mem_nodes}")
    print("\nDemonstration complete.")

if __name__ == "__main__":
    main()
