
import json
import re

from ollama import chat
from agent.tools import lookup_order


MODEL = "qwen2.5:3b"
MAX_STEPS = 5


def lookup_order_tool(order_id: int) -> str:
    """Look up a real shop order using its order ID."""
    result = lookup_order(order_id)
    return json.dumps(result, ensure_ascii=False)


# Only registered functions can be executed by the agent.
AVAILABLE_TOOLS = {
    "lookup_order_tool": lookup_order_tool,
}


def run_agent(user_question: str) -> dict:
    """Run the support agent and return its answer and tool trace."""

    # Reject explicitly invalid order IDs before calling the model.
    invalid_id_match = re.search(
        r"\border\s+(?:id|number)\s*[:#]?\s*([^\s,!?;]+)",
        user_question,
        re.IGNORECASE,
    )

    if invalid_id_match:
        order_id_text = invalid_id_match.group(1).rstrip(".,:")

        if not order_id_text.isdigit():
            return {
                "answer": (
                    f"The provided order ID '{order_id_text}' "
                    "is not a valid integer. Please provide a "
                    "valid integer order ID."
                ),
                "tool_trace": [],
            }

    
    
    system_prompt = (
        "You are TrustAgent, a customer support assistant. "

        "Use lookup_order_tool whenever a question requires "
        "checking an order. Only report facts returned by the tool. "
        "If an order is not found, say so. "

        "Never claim you performed an action unless an available "
        "tool actually performed it. You may only look up orders. "
        "You cannot process refunds, cancel orders, or change "
        "delivery addresses. Only use tools that are actually available. "

        "If a user requests an unsupported action, explicitly "
        "explain that you cannot perform it. Never imply that you "
        "can perform the action, that it was attempted, or that "
        "it was completed. You may look up an order to provide "
        "relevant information, but a lookup does not perform "
        "a refund, cancellation, or address change. "

        "If an order ID is invalid, do not call the lookup tool, "
        "guess a replacement ID, or invent order details. Explain "
        "that the ID must be a valid integer. "

        "If the user requests an order lookup but does not provide "
        "an order ID, ask which order they mean and request the ID. "

        "If the user requests an unsupported order-specific action "
        "without providing an order ID, first explicitly refuse "
        "the unsupported action, then ask for the order ID only "
        "if it would be useful to provide permitted order information. "

        "For a request such as 'Refund my order', respond with a "
        "clear refusal and ask which order they mean. For example: "
        "'I cannot process refunds. Which order would you like "
        "help with? Please provide your order ID.' "

        "For a request such as 'Change my address, please', clearly "
        "state that you cannot change delivery addresses. Do not "
        "say that you can assist with changing the address. If "
        "appropriate, offer to look up order information instead. "
        "For example: 'I cannot change delivery addresses. If you "
        "need help checking an order, please provide your order ID.' "

        "If the user requests an unsupported action together with "
        "order information, provide verified order information "
        "when available and explicitly refuse the unsupported "
        "action. Never claim that the unsupported action was performed. "

        "If the request is ambiguous, ask a clarifying question "
        "without promising unsupported capabilities. "

        "Do not invent a currency symbol or currency code. "
        "The amount field is a numeric value, and its currency "
        "is not explicitly provided by the tool. If mentioning "
        "the amount, report the numeric value without adding "
        "a currency symbol or code. "
    )



    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    tool_trace = []

    # Cache results for this request only.
    # Keys are integer order IDs; values are JSON strings.
    lookup_cache = {}

    # Automatically look up an explicitly provided numeric order ID.
    # This ensures the agent has verified order information.
    order_match = re.search(
        r"\border(?:\s+(?:id|number))?\s*[:#]?\s*(\d+)\b",
        user_question,
        re.IGNORECASE,
    )

    if order_match:
        order_id = int(order_match.group(1))

        lookup_result = lookup_order_tool(order_id)
        lookup_cache[order_id] = lookup_result

        tool_trace.append(
            {
                "tool": "lookup_order_tool",
                "arguments": {"order_id": order_id},
                "result": lookup_result,
            }
        )

        messages[0]["content"] += (
            "\n\nA verified order lookup has already been performed "
            "for this request. The result is: "
            + lookup_result
            + "\nUse these verified facts when answering. "
            "Do not ask for an order ID that the user already provided. "
            "Clearly refuse any requested refund, cancellation, or "
            "address change because those actions are unsupported. "
            "Never claim an unsupported action was performed. "
            "If you request lookup_order_tool for an order ID whose "
            "result is already supplied, the result can be reused. "
            "Do not repeat a lookup unnecessarily."
        )

    # Agent reasoning and tool execution loop.
    for step in range(MAX_STEPS):
        response = chat(
            model=MODEL,
            messages=messages,
            tools=[lookup_order_tool],
        )

        # Preserve the assistant message and any tool calls.
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
                result = {
                    "success": False,
                    "error": "Unknown tool.",
                }

            elif name == "lookup_order_tool":
                # Reuse an existing result instead of querying
                # the database a second time for the same order.
                try:
                    raw_order_id = arguments.get("order_id")
                    order_id = int(raw_order_id)

                    if isinstance(raw_order_id, bool):
                        raise ValueError("Invalid order ID")

                    if isinstance(raw_order_id, float):
                        raise ValueError("Invalid order ID")

                    if order_id in lookup_cache:
                        result = lookup_cache[order_id]

                        print(
                            "Reusing cached lookup result for "
                            f"order {order_id}."
                        )

                    else:
                        result = function(order_id=order_id)
                        lookup_cache[order_id] = result

                        # Record only an actual tool execution.
                        tool_trace.append(
                            {
                                "tool": name,
                                "arguments": {
                                    "order_id": order_id
                                },
                                "result": result,
                            }
                        )

                except (TypeError, ValueError):
                    result = json.dumps(
                        {
                            "success": False,
                            "error": "Invalid tool arguments.",
                        }
                    )

                except Exception:
                    result = json.dumps(
                        {
                            "success": False,
                            "error": "Tool execution failed.",
                        }
                    )

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

                tool_trace.append(
                    {
                        "tool": name,
                        "arguments": arguments,
                        "result": result,
                    }
                )

            print(f"Tool result: {result}")

            # Always send a tool result back to the model,
            # including when a cached result was reused.
            messages.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    "content": (
                        result
                        if isinstance(result, str)
                        else json.dumps(
                            result,
                            ensure_ascii=False,
                        )
                    ),
                }
            )

    return {
        "answer": (
            "I couldn't complete the request within the step limit."
        ),
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
            print(
                "Check that Ollama is running "
                "and the model is available."
            )
