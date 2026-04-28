# Adding LLM Providers

Tiny Code Agent keeps provider-specific API details out of the core agent loop. The core loop depends only on the LLMClient protocol in src/tiny_code_agent/llm.py.

## Provider Contract

A provider adapter must implement:

- complete(model, messages, tools, instructions) -> AssistantTurn
- tool_result_message(result) -> Message
- provider_name

complete should translate repo-native Tool objects into the provider tool schema, call the provider API, and normalize the response into:

- AssistantTurn.messages: provider messages/items that must be kept in conversation history
- AssistantTurn.text: final assistant text, if no tool call is requested
- AssistantTurn.tool_calls: normalized tool calls with id, name, and parsed arguments

tool_result_message should translate a local tool result back into the message shape that provider expects.

## Files To Add Or Change

1. Add a provider module, for example src/tiny_code_agent/providers/anthropic.py.
2. Implement an adapter class that satisfies LLMClient.
3. Register it in src/tiny_code_agent/providers/factory.py.
4. Add provider-specific environment variable checks in src/tiny_code_agent/cli.py.
5. Add tests for model defaults, unsupported providers, and adapter message conversion.

## Current Provider

- openai: implemented with the Responses API

## Future Provider Notes

- Anthropic: map tools to Claude tool-use blocks and tool-result blocks.
- DeepSeek: if using an OpenAI-compatible API, reuse most of the OpenAI adapter behind a configurable base URL.
