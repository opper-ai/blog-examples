# GitHub PR Reviewer

This example demonstrates how to use the Agent Runner service with the ReAct pattern to review GitHub pull requests.

## Requirements

- Python 3.9+
- [Opper AI](https://opper.ai) API key 
- GitHub token (optional, for accessing private repositories)

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up your environment variables:

```bash
# Create a .env file with your API keys
echo "OPPER_API_KEY=your_opper_api_key" > .env
echo "GITHUB_TOKEN=your_github_token" >> .env
```

## Usage

### GitHub PR Review

```bash
python main.py pr-review OWNER REPO PR_NUMBER [-v]
```

Arguments:
- `OWNER`: Repository owner (username or organization)
- `REPO`: Repository name
- `PR_NUMBER`: Pull request number to review
- `-v/--verbose`: Show the agent's thought process

Example:
```bash
python main.py pr-review openai gpt-4 1234 -v
```

## Tool Architecture

This example contains a GitHub PR Tool that allows agents to fetch and review GitHub pull requests.

The tool follows this architecture pattern:
- Input schema defined using Pydantic models
- Main tool class with an `execute` method
- Helper methods for specific API operations

The tool is integrated into the ReAct pattern via the Agent Runner, which:
1. Starts with a reasoning step to analyze the current state
2. Selects the next action to take
3. Executes the action and observes the result
4. Repeats until a solution is found

## Extending the Example

You can extend this example by:

1. Adding more operations to the existing tool
2. Creating new tools that interact with other APIs
3. Customizing the agent instructions for different use cases
4. Adding more detailed Pydantic schemas for input validation and type safety

## License

[MIT License](LICENSE) 