"""
Example script for reviewing GitHub pull requests using the ReAct pattern.
"""

import argparse
import asyncio
import logging
import os

from agent_runner import AgentRunnerService
from dotenv import load_dotenv
from github_pr_tool import GitHubPRTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Agent configuration
PR_REVIEW_AGENT = {
    "instructions": """
    You are a GitHub PR reviewer. Your task is to review pull requests and provide helpful feedback.
    You should:
    1. Fetch the PR information using the github_pr_tool
    2. Analyze the changes and their impact
    3. Identify potential issues or improvements
    4. Provide a detailed review with actionable feedback
    
    Your final output should include:
    - A summary of the changes
    - List of issues found (if any)
    - Suggestions for improvement
    - Overall assessment
    """,
    "verbose": False,  # Will be set from command line args
}


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Review a GitHub PR using an AI agent")

    # GitHub PR Review command
    parser.add_argument("owner", help="Repository owner (username or organization)")
    parser.add_argument("repo", help="Repository name")
    parser.add_argument("pr_number", type=int, help="Pull request number to review")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show agent's thought process"
    )

    args = parser.parse_args()

    # Initialize services
    agent_runner = AgentRunnerService()

    # Update agent config with verbose setting
    PR_REVIEW_AGENT["verbose"] = args.verbose

    # Initialize GitHub PR tool
    github_token = os.getenv("GITHUB_TOKEN")
    github_pr_tool = GitHubPRTool(github_token)

    # Register tools
    agent_runner.register_tools({"github_pr_tool": github_pr_tool.execute})

    # Prepare input data
    input_data = {
        "owner": args.owner,
        "repo": args.repo,
        "pr_number": args.pr_number,
    }

    try:
        # Run the agent
        result = await agent_runner.run_agent(
            agent_id="github_pr_reviewer",
            agent=PR_REVIEW_AGENT,
            input_data=input_data,
        )

        # Check for errors
        if "error" in result:
            print(f"Error: {result['error']}")
            return

        # Print the review
        print("\n=== PR Review Results ===")
        print(f"\nSummary: {result.get('review_summary', 'No summary provided')}")

        if issues := result.get("issues_found"):
            print("\nIssues Found:")
            for issue in issues:
                print(f"- {issue}")

        if suggestions := result.get("suggestions"):
            print("\nSuggestions:")
            for suggestion in suggestions:
                print(f"- {suggestion}")

        print(
            f"\nOverall Assessment: {result.get('overall_assessment', 'No assessment provided')}"
        )

    except Exception as e:
        print(f"Error running the agent: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
