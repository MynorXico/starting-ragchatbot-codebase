import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator

# --- Helpers to build mock Anthropic response objects ---


def make_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block(tool_name, tool_input, tool_id="tool_123"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    return block


def make_response(content_blocks, stop_reason="end_turn"):
    response = MagicMock()
    response.content = content_blocks
    response.stop_reason = stop_reason
    return response


# --- Fixtures ---


@pytest.fixture
def generator():
    with patch("ai_generator.anthropic") as mock_anthropic:
        gen = AIGenerator(api_key="test-key", model="test-model")
        yield gen, mock_anthropic


# --- Tests ---


class TestDirectResponse:

    def test_returns_text_when_no_tool_use(self, generator):
        gen, _ = generator
        gen.client.messages.create.return_value = make_response(
            [make_text_block("Hello, this is a direct answer.")],
            stop_reason="end_turn",
        )

        result = gen.generate_response(query="What is Python?")

        assert result == "Hello, this is a direct answer."

    def test_no_tools_passed_means_no_tool_choice(self, generator):
        gen, _ = generator
        gen.client.messages.create.return_value = make_response(
            [make_text_block("answer")]
        )

        gen.generate_response(query="question", tools=None)

        call_kwargs = gen.client.messages.create.call_args[1]
        assert "tools" not in call_kwargs
        assert "tool_choice" not in call_kwargs

    def test_tools_passed_sets_tool_choice_auto(self, generator):
        gen, _ = generator
        gen.client.messages.create.return_value = make_response(
            [make_text_block("answer")]
        )
        tools = [{"name": "test_tool", "input_schema": {}}]
        tool_manager = MagicMock()

        gen.generate_response(query="question", tools=tools, tool_manager=tool_manager)

        call_kwargs = gen.client.messages.create.call_args[1]
        assert call_kwargs["tools"] == tools
        assert call_kwargs["tool_choice"] == {"type": "auto"}


class TestToolExecution:

    def test_tool_use_triggers_tool_manager_execution(self, generator):
        gen, _ = generator
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search results here"

        tool_response = make_response(
            [make_tool_use_block("search_course_content", {"query": "MCP"})],
            stop_reason="tool_use",
        )
        final_response = make_response(
            [make_text_block("MCP is about model context protocol.")]
        )
        gen.client.messages.create.side_effect = [tool_response, final_response]

        tools = [{"name": "search_course_content", "input_schema": {}}]
        result = gen.generate_response(
            query="What is MCP?", tools=tools, tool_manager=tool_manager
        )

        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="MCP"
        )
        assert result == "MCP is about model context protocol."

    def test_tool_result_sent_back_with_correct_id(self, generator):
        gen, _ = generator
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "tool output"

        tool_response = make_response(
            [
                make_tool_use_block(
                    "search_course_content", {"query": "test"}, tool_id="call_abc"
                )
            ],
            stop_reason="tool_use",
        )
        final_response = make_response([make_text_block("final")])
        gen.client.messages.create.side_effect = [tool_response, final_response]

        gen.generate_response(query="q", tools=[{}], tool_manager=tool_manager)

        # The second API call should have the tool result in messages
        second_call_kwargs = gen.client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        tool_result_msg = messages[-1]
        assert tool_result_msg["role"] == "user"
        assert tool_result_msg["content"][0]["type"] == "tool_result"
        assert tool_result_msg["content"][0]["tool_use_id"] == "call_abc"
        assert tool_result_msg["content"][0]["content"] == "tool output"

    def test_single_round_returns_text_on_second_call(self, generator):
        """When Claude uses a tool once and returns text on the next call, the text is returned."""
        gen, _ = generator
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        tool_response = make_response(
            [make_tool_use_block("search_course_content", {"query": "x"})],
            stop_reason="tool_use",
        )
        final_response = make_response([make_text_block("final answer")])
        gen.client.messages.create.side_effect = [tool_response, final_response]

        result = gen.generate_response(
            query="q", tools=[{"name": "t"}], tool_manager=tool_manager
        )

        assert result == "final answer"
        assert gen.client.messages.create.call_count == 2

    def test_conversation_history_appended_to_system(self, generator):
        gen, _ = generator
        gen.client.messages.create.return_value = make_response(
            [make_text_block("answer")]
        )

        gen.generate_response(
            query="q", conversation_history="User: hi\nAssistant: hello"
        )

        call_kwargs = gen.client.messages.create.call_args[1]
        assert "Previous conversation:" in call_kwargs["system"]
        assert "User: hi" in call_kwargs["system"]


class TestMultiRoundToolCalling:

    def test_two_round_sequential_tool_calls(self, generator):
        """Claude calls get_course_outline, then search_course_content, then synthesizes."""
        gen, _ = generator
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = [
            "Course outline: Lesson 4 is about Agents",
            "Content about agents from other courses",
        ]

        # Round 1: Claude calls get_course_outline
        round1_response = make_response(
            [
                make_tool_use_block(
                    "get_course_outline", {"course_name": "MCP"}, tool_id="call_1"
                )
            ],
            stop_reason="tool_use",
        )
        # Round 2: Claude calls search_course_content
        round2_response = make_response(
            [
                make_tool_use_block(
                    "search_course_content", {"query": "Agents"}, tool_id="call_2"
                )
            ],
            stop_reason="tool_use",
        )
        # Final synthesis (post-loop, no tools)
        final_response = make_response(
            [
                make_text_block(
                    "Lesson 4 of MCP covers Agents. Other courses also discuss this."
                )
            ]
        )
        gen.client.messages.create.side_effect = [
            round1_response,
            round2_response,
            final_response,
        ]

        tools = [{"name": "get_course_outline"}, {"name": "search_course_content"}]
        result = gen.generate_response(
            query="q", tools=tools, tool_manager=tool_manager
        )

        # Both tools should have been executed
        assert tool_manager.execute_tool.call_count == 2
        tool_manager.execute_tool.assert_any_call(
            "get_course_outline", course_name="MCP"
        )
        tool_manager.execute_tool.assert_any_call(
            "search_course_content", query="Agents"
        )
        # 3 API calls total
        assert gen.client.messages.create.call_count == 3
        assert (
            result == "Lesson 4 of MCP covers Agents. Other courses also discuss this."
        )

    def test_max_rounds_forces_synthesis_without_tools(self, generator):
        """After max_tool_rounds of tool calls, the final API call should NOT include tools."""
        gen, _ = generator
        gen.max_tool_rounds = 2
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "some result"

        # Both rounds return tool_use
        round1 = make_response(
            [
                make_tool_use_block(
                    "search_course_content", {"query": "a"}, tool_id="c1"
                )
            ],
            stop_reason="tool_use",
        )
        round2 = make_response(
            [
                make_tool_use_block(
                    "search_course_content", {"query": "b"}, tool_id="c2"
                )
            ],
            stop_reason="tool_use",
        )
        synthesis = make_response([make_text_block("synthesized")])
        gen.client.messages.create.side_effect = [round1, round2, synthesis]

        result = gen.generate_response(
            query="q", tools=[{"name": "t"}], tool_manager=tool_manager
        )

        # The 3rd (final) API call should NOT have tools
        final_call_kwargs = gen.client.messages.create.call_args_list[2][1]
        assert "tools" not in final_call_kwargs
        assert "tool_choice" not in final_call_kwargs
        assert result == "synthesized"

    def test_second_round_includes_tools(self, generator):
        """The second API call (after round 1 tool use) should still include tools."""
        gen, _ = generator
        gen.max_tool_rounds = 2
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        round1 = make_response(
            [make_tool_use_block("search_course_content", {"query": "x"})],
            stop_reason="tool_use",
        )
        # Round 2 returns text (no further tool use)
        round2 = make_response([make_text_block("answer")])
        gen.client.messages.create.side_effect = [round1, round2]

        gen.generate_response(
            query="q", tools=[{"name": "t"}], tool_manager=tool_manager
        )

        # The second API call should include tools (Claude could have called another)
        second_call_kwargs = gen.client.messages.create.call_args_list[1][1]
        assert "tools" in second_call_kwargs

    def test_single_round_backward_compatible(self, generator):
        """Single tool call followed by text works identically to the old behavior."""
        gen, _ = generator
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search results"

        tool_response = make_response(
            [make_tool_use_block("search_course_content", {"query": "tool use"})],
            stop_reason="tool_use",
        )
        text_response = make_response([make_text_block("Tool use is...")])
        gen.client.messages.create.side_effect = [tool_response, text_response]

        result = gen.generate_response(
            query="What is tool use?",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )

        assert result == "Tool use is..."
        assert tool_manager.execute_tool.call_count == 1
        assert gen.client.messages.create.call_count == 2


class TestExceptionHandling:

    def test_api_exception_propagates(self, generator):
        gen, _ = generator
        gen.client.messages.create.side_effect = Exception("API connection failed")

        with pytest.raises(Exception, match="API connection failed"):
            gen.generate_response(query="test")

    def test_tool_error_returns_graceful_response(self, generator):
        """Tool exception is caught, sent as is_error tool_result, and Claude responds gracefully."""
        gen, _ = generator
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("Tool crashed")

        tool_response = make_response(
            [
                make_tool_use_block(
                    "search_course_content", {"query": "x"}, tool_id="call_err"
                )
            ],
            stop_reason="tool_use",
        )
        # After error, Claude synthesizes a graceful response
        graceful_response = make_response(
            [make_text_block("I was unable to retrieve that information.")]
        )
        gen.client.messages.create.side_effect = [tool_response, graceful_response]

        result = gen.generate_response(query="q", tools=[{}], tool_manager=tool_manager)

        # Should return Claude's graceful response, not raise
        assert result == "I was unable to retrieve that information."
        # The error tool_result should have been sent to Claude
        second_call_kwargs = gen.client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        tool_result_msg = messages[-1]
        error_result = tool_result_msg["content"][0]
        assert error_result["is_error"] is True
        assert "Tool execution failed" in error_result["content"]
        assert error_result["tool_use_id"] == "call_err"
        # Final call should NOT include tools (broke out of loop)
        assert "tools" not in second_call_kwargs

    def test_no_tool_manager_skips_tool_execution(self, generator):
        """If stop_reason is tool_use but no tool_manager provided, return text content."""
        gen, _ = generator
        text_block = make_text_block("I want to search")
        tool_block = make_tool_use_block("search_course_content", {"query": "x"})
        response = make_response([text_block, tool_block], stop_reason="tool_use")
        gen.client.messages.create.return_value = response

        result = gen.generate_response(query="q", tools=[{}], tool_manager=None)

        assert result == "I want to search"
