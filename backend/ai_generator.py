import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Available Tools:
1. **search_course_content** - Search within course content for specific topics, concepts, explanations, or details.
2. **get_course_outline** - Retrieve a course's outline including its title, course link, and full list of lessons with lesson numbers and titles.

Tool Usage Rules:
- **Up to two tool calls per query** — you may call tools sequentially when a follow-up search depends on results from a prior tool call (e.g., first retrieve a course outline to identify a lesson topic, then search for that topic across other courses)
- If a single tool call is sufficient, do not make a second call
- Use `get_course_outline` for structural questions: "What lessons are in X?", "Show me the outline of Y", "What does course Z cover?", "List the lessons in X"
- Use `search_course_content` for content questions: "How does X work?", "What does the course say about Y?", "Explain the concept of Z from the course"
- If a tool yields no results, state this clearly without offering alternatives
- Synthesize tool results into accurate, fact-based responses
- When presenting course outlines, include the course title, course link, and the number and title of each lesson

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course-specific questions**: Use the appropriate tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the outline"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str, max_tool_rounds: int = 2):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tool_rounds = max_tool_rounds

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional multi-round tool usage and conversation context.

        Supports up to max_tool_rounds sequential tool calls. Each round is a separate
        API call where Claude can reason about previous results and decide to call
        another tool or produce a final answer.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]

        # Tool-calling loop: each iteration is one API call that may request a tool
        for round_number in range(self.max_tool_rounds):
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content
            }

            # Include tools so Claude can decide to call one
            if tools and tool_manager:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            response = self.client.messages.create(**api_params)

            # If Claude didn't request a tool, return the text response
            if response.stop_reason != "tool_use" or not tool_manager:
                return response.content[0].text

            # Claude wants to use a tool — execute it
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            tool_failed = False
            for content_block in response.content:
                if content_block.type == "tool_use":
                    try:
                        tool_result = tool_manager.execute_tool(
                            content_block.name,
                            **content_block.input
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": f"Tool execution failed: {e}",
                            "is_error": True
                        })
                        tool_failed = True

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # On tool failure, break out and force a synthesis without tools
            if tool_failed:
                break

        # Loop exhausted (all rounds used) or broke on error
        # Final call WITHOUT tools to force a text response
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }

        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text
