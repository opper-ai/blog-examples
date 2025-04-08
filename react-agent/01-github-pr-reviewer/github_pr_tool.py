"""
GitHub PR review tool for the agent runner system.

This tool enables agents to fetch and review GitHub pull requests.
"""

import logging
from typing import Any, Dict, List, Optional

import aiohttp
from opperai import AsyncOpper, trace
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
opper = AsyncOpper()


class GitHubPRToolInput(BaseModel):
    """Input schema for the GitHub PR review tool."""

    owner: str = Field(..., description="Repository owner (username or organization)")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull request number to review")
    focus_area: Optional[str] = Field(
        None,
        description="Specific area to focus review on (e.g., 'performance', 'security', 'style')",
    )


class GitHubPRTool:
    """Tool for interacting with GitHub PRs."""

    def __init__(self, github_token: Optional[str] = None):
        """Initialize the GitHub PR tool.

        Args:
            github_token: Optional GitHub personal access token. If not provided,
                        only public repositories will be accessible with rate limits.
        """
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"

    @trace(name="github_pr_tool.execute")
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the GitHub PR tool."""
        # Record the input parameters in the span
        await opper.traces.current_span.update(input=str(params))

        try:
            # Check for required parameters
            required_params = ["owner", "repo", "pr_number"]
            missing_params = [param for param in required_params if param not in params]

            if missing_params:
                error_result = {
                    "error": f"Missing required parameters: {', '.join(missing_params)}. Please provide owner, repo, and pr_number.",
                    "status": "error",
                }
                # Record the error output in the span
                await opper.traces.current_span.update(output=str(error_result))
                return error_result

            # Get PR information
            pr_info = await self._get_pr_info(
                params["owner"], params["repo"], params["pr_number"]
            )

            # Check if repository is private and we're not authenticated
            if pr_info.get("private", False) and "Authorization" not in self.headers:
                error_result = {
                    "error": "This is a private repository. A GitHub token is required for access.",
                    "status": "error",
                }
                # Record the error output in the span
                await opper.traces.current_span.update(output=str(error_result))
                return error_result

            # Get PR files and diff
            files = await self._get_pr_files(
                params["owner"], params["repo"], params["pr_number"]
            )
            diff = await self._get_pr_diff(
                params["owner"], params["repo"], params["pr_number"]
            )

            # Build the result
            result = {
                "pr_title": pr_info["title"],
                "pr_author": pr_info["user"]["login"],
                "changed_files": [f["filename"] for f in files],
                "additions": pr_info["additions"],
                "deletions": pr_info["deletions"],
                "diff": self._truncate_diff(diff),
                "pr_description": pr_info["body"] or "",
                "pr_url": pr_info["html_url"],
                "repository_private": pr_info.get("private", False),
                "status": "success",
            }

            # Record the output result in the span
            await opper.traces.current_span.update(output=str(result))
            return result
        except aiohttp.ClientResponseError as e:
            error_msg = str(e)
            if e.status == 404:
                error_msg = f"PR not found: {params.get('owner', '')}/{params.get('repo', '')}#{params.get('pr_number', '')}"
            elif e.status == 403 and "rate limit exceeded" in str(e).lower():
                error_msg = "GitHub API rate limit exceeded. Consider adding authentication for higher limits."
            logger.error(f"GitHub API error: {error_msg}")
            error_result = {"error": error_msg, "status": "error"}

            # Record the error output in the span
            await opper.traces.current_span.update(output=str(error_result))
            return error_result
        except Exception as e:
            logger.error(f"Error executing GitHub PR tool: {e}", exc_info=True)
            error_result = {
                "error": f"Error retrieving PR information: {str(e)}",
                "status": "error",
            }

            # Record the error output in the span
            await opper.traces.current_span.update(output=str(error_result))
            return error_result

    async def _get_pr_info(
        self, owner: str, repo: str, pr_number: int
    ) -> Dict[str, Any]:
        """Get information about a pull request."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                return await response.json()

    async def _get_pr_files(
        self, owner: str, repo: str, pr_number: int
    ) -> List[Dict[str, Any]]:
        """Get files changed in a pull request."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                return await response.json()

    async def _get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Get the diff of a pull request."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.text()

    def _truncate_diff(self, diff: str, max_length: int = 50000) -> str:
        """Truncate the diff if it's too long."""
        if len(diff) > max_length:
            return diff[:max_length] + "\n... (diff truncated for length)"
        return diff
