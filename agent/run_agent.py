
import json
import re
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
    # Reject explicitly invalid order IDs before calling the model.
    match = re.search(
        r"\border\s*(?:id|number)\s*[:#]?\s*([^\s,!?;]+)",
        user_question,
        re.IGNORECASE,
    )

    if match:
        order_id_text = match.group(1).rstrip(".,:")

        if not order_id_text.isdigit():
            return {
                "answer": (
                    f"The provided order ID '{order_id_text}' "
                    "is not a valid integer. Please provide a "
                    "valid integer order ID."
                ),
                "tool_trace": [],
            }
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
                "Only use the tools that are actually available."
                "You can look up orders, but you cannot cancel orders, process refunds, or change delivery addresses."
                "Never claim that you performed an action unless an available tool actually performed it."
                "If a user requests an unsupported action, clearly explain that you cannot perform that action. You may look up an order to provide relevant information, but do not imply that the requested action was attempted."
                "If the user provides an order ID that is not a valid integer, do not call the lookup tool and do not invent, replace, or guess an order ID. Explain that the ID must be a valid integer."
                "If an order ID is missing and is necessary to answer a lookup question, ask the user for it."
                "If the request is ambiguous, ask a clarifying question without promising unsupported capabilities."
                "When an order lookup is performed for a request involving an "
                "unsupported action, clearly state that the requested action "
                "cannot be performed, even if you also provide order details. "

                "When the user asks for order information and an unsupported "
                "action together, provide the verified order information and "
                "explicitly refuse the unsupported action. "

                "When the user requests an unsupported action without specifying "
                "an order ID, clearly refuse that action and ask a relevant "
                "clarifying question if needed. "
            ),
        },
        {"role": "user", "content": user_question},
    ]

    tool_trace = []
    # Automatically look up an explicitly provided numeric order ID.
    # This avoids relying on the model to choose the lookup tool.
    order_match = re.search(
        r"\border(?:\s+(?:id|number))?\s*[:#]?\s*(\d+)\b",
        user_question,
        re.IGNORECASE,
    )

    if order_match:
        order_id = int(order_match.group(1))
        lookup_result = lookup_order_tool(order_id)

        tool_trace.append({
            "tool": "lookup_order_tool",
            "arguments": {"order_id": order_id},
            "result": lookup_result,
        })

        messages[0]["content"] += (
            "\n\nA verified order lookup has already been performed "
            "for this request. The result is: "
            + lookup_result
            + "\nUse these verified facts when answering. Do not ask "
            "for an order ID that the user already provided. "
            "Clearly refuse any requested refund, cancellation, or "
            "address change because those actions are unsupported. "
            "Never claim an unsupported action was performed. "
            "Do not call the lookup tool again for this same order."
        )


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
