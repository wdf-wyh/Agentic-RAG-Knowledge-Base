#!/usr/bin/env python3
from src.agent.tools.web_tools import WebSearchTool

# Test DuckDuckGo search
tool = WebSearchTool(provider='duckduckgo')
result = tool.execute(query='广州天气', max_results=5)
print('Success:', result.success)
print('Output:', result.output)
print('Error:', result.error)
