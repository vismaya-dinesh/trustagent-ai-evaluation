
import json

from ollama import chat
from agent.tools import lookup_order


MODEL = "qwen2.5:3b"
MAX_STEPS = 5


def lookup_order_tool(order_id: int) -> str:
    """Look up a real shop order using its order ID.

    Args:
        order_id: The integer ID of the order to find.

    Returns:
        The order details or an error, as a JSON string.
    """
    result = lookup_order(order_id)
    return json.dumps(result, ensure_ascii=False)


# Only registered functions can be executed by the agent.
AVAILABLE_TOOLS = {
    "lookup_order_tool": lookup_order_tool,
}


def run_agent(user_question: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are TrustAgent, a customer support assistant. "
                "Use lookup_order_tool whenever a question requires "
                "checking an order. Only report facts returned by "
                "the tool. If an order is not found, say so. "
                "Never claim you performed an action unless a tool "
                "actually performed it. You may only look up orders; "
                "you cannot issue refunds or change orders yet."
            ),
        },
        {"role": "user", "content": user_question},
    ]

    tool_trace = []

    for step in range(MAX_STEPS):
        response = chat(
            model=MODEL,
            messages=messages,
            tools=[lookup_order_tool],
        )

        # Keep the assistant's response, including any tool calls.
        messages.append(response.message)

        tool_calls = response.message.tool_calls or []

        # No more tools requested: the agent has finished.
        if not tool_calls:
            return {
                "answer": response.message.content or "",
                "tool_trace": tool_trace,
            }

        for tool_call in tool_calls:
            name = tool_call.function.name
            arguments = tool_call.function.arguments

            

            print(f"\n[Step {step + 1}] Tool requested: {name}")
            print(f"Arguments: {arguments}")

            function = AVAILABLE_TOOLS.get(name)

            if function is None:
                result = {"success": False, "error": "Unknown tool."}
            else:
                try:
                    result = function(**arguments)
                except (TypeError, ValueError):
                    result = {
                        "success": False,
                        "error": "Invalid tool arguments.",
                    }
                except Exception:
                    result = {
                        "success": False,
                        "error": "Tool execution failed.",
                    }

            print(f"Tool result: {result}")

            
            tool_trace.append({
                "tool": name,
                "arguments": arguments,
                "result": result,
            })


            messages.append({
                "role": "tool",
                "tool_name": name,
                "content": (
                    result
                    if isinstance(result, str)
                    else json.dumps(result)
                ),
            })

    return {
    "answer": "I couldn't complete the request within the step limit.",
    "tool_trace": tool_trace,
    }


if __name__ == "__main__":
    print("=== TrustAgent ===")
    print("Ask about an order, or type 'exit' to quit.")

    while True:
        question = input("\nYou: ").strip()

        if question.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if not question:
            continue

        try:
            result = run_agent(question)
            print(f"\nTrustAgent: {result['answer']}")  
        except Exception as error:
            print(f"\nSomething went wrong: {error}")
            print("Check that Ollama is running and the model is available.")
