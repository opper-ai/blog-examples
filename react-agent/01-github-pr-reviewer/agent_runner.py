"""
Agent runner service that implements the ReAct pattern.

This service handles the execution of agents following the Reasoning-Acting-Observation loop
with LLM-based reasoning and actions.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from opperai import AsyncOpper, trace
from pydantic import BaseModel, Field, field_validator

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Opper client
opper = AsyncOpper()


class AgentReasoning(BaseModel):
    """Model for agent's reasoning step output."""

    content: str = Field(
        ..., description="The agent's reasoning about the current state"
    )
    confidence: float = Field(
        ...,
        description="A score from 0.0 to 1.0 indicating your confidence in the reasoning",
        ge=0.0,
        le=1.0,
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v


class AgentAction(BaseModel):
    """Model for agent's action selection output."""

    action_type: str = Field(..., description="Type of action: 'use_tool' or 'finish'")
    tool_name: Optional[str] = Field(None, description="Name of the tool to use")
    tool_params: Optional[Dict[str, Any]] = Field(
        None, description="Parameters for the tool"
    )
    output: Optional[Dict[str, Any]] = Field(
        None, description="Final output if finishing"
    )


class AgentOutput(BaseModel):
    """Model for the final PR review output."""

    review_summary: str = Field(..., description="Summary of the PR changes")
    issues_found: List[str] = Field(
        default_factory=list, description="List of issues found"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="List of suggestions"
    )
    overall_assessment: str = Field(..., description="Overall assessment of the PR")


def to_json_str(obj: Any) -> str:
    """Convert an object to a formatted JSON string."""
    try:
        return json.dumps(obj, indent=2)
    except (TypeError, ValueError):
        return str(obj)


class AgentRunnerService:
    """Service for running agents using the ReAct pattern."""

    def __init__(self):
        self.tools = {}
        self.max_steps = 15

    def register_tools(self, tools: Dict[str, Any]) -> None:
        """Register tools that the agent can use."""
        self.tools = tools
        logger.info(f"Registered {len(tools)} tools: {', '.join(tools.keys())}")

    @trace(name="agent_runner.run_agent")
    async def run_agent(
        self, agent_id: str, agent: Dict[str, Any], input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run an agent with the given input data."""
        # Keep reference to the root span
        root_span = opper.traces.current_span
        root_span_id = root_span.uuid
        logger.info(f"Root span ID: {root_span_id}")

        # Record input in the root span, including agent ID and instructions
        agent_input = {
            "agent_id": agent_id,
            "agent_instructions": agent.get("instructions", ""),
            "input_data": input_data,
        }
        await root_span.update(input=to_json_str(agent_input))

        context = {
            "input": input_data,
            "thoughts": [],
            "current_step": 0,
            "intermediate_results": {},
        }

        # Get verbose setting from agent config
        verbose = agent.get("verbose", False)
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1
            context["current_step"] = current_step

            # Start a span for this ReAct cycle
            async with opper.traces.start(
                name=f"react_cycle_{current_step}"
            ) as cycle_span:
                # Add the context as input to the cycle span
                await cycle_span.update(input=to_json_str(context))

                # Step 1: REASONING - Analyze the current state
                reasoning = await self._react_reasoning(agent, context)
                if verbose:
                    print(f"\n=== Step {current_step} - REASONING ===")
                    print(reasoning.content)
                    print(f"Confidence: {reasoning.confidence:.2f}")

                # Save confidence as a metric
                await cycle_span.save_metric(
                    dimension="reasoning_confidence",
                    value=reasoning.confidence,
                    comment=f"Agent's confidence in its reasoning for step {current_step}",
                )

                # Step 2: ACTION SELECTION - Select the next action
                action = await self._react_action_selection(agent, context, reasoning)
                if verbose and action.tool_name:
                    print(f"\n=== Step {current_step} - ACTION ===")
                    print(f"Selected tool: {action.tool_name}")
                    print(f"Parameters: {action.tool_params or {}}")

                # If the action is to finish, we're done
                if action.action_type == "finish":
                    if verbose:
                        print("\n=== FINISHED ===")

                    final_output = action.output or {}

                    # Log the final output for debugging
                    logger.info(f"Final output: {final_output}")

                    # Update cycle span with the final output
                    await cycle_span.update(output=to_json_str(final_output))

                    # Update root span with the final output directly using our saved reference
                    try:
                        await root_span.update(output=to_json_str(final_output))
                        logger.info(
                            f"Updated root span {root_span_id} with final output"
                        )
                    except Exception as e:
                        logger.error(f"Error updating root span: {e}")

                    return final_output

                # Step 3: OBSERVATION - Execute the selected tool
                if action.action_type == "use_tool" and action.tool_name:
                    tool_name = action.tool_name
                    tool_params = action.tool_params or {}

                    # Execute the tool
                    if tool_name not in self.tools:
                        error = f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}"
                        logger.error(error)
                        error_result = {"error": error}

                        # Update root span with the error directly
                        try:
                            await root_span.update(output=to_json_str(error_result))
                        except Exception as e:
                            logger.error(f"Error updating root span: {e}")

                        return error_result

                    try:
                        # Check if we have a Pydantic model in the parameters
                        # that needs to be converted to a dict
                        for key, value in tool_params.items():
                            if hasattr(value, "model_dump"):
                                tool_params[key] = value.model_dump()

                        # Execute the tool
                        result = await self.tools[tool_name](tool_params)

                        observation = str(result)
                        if verbose:
                            print(f"\n=== Step {current_step} - OBSERVATION ===")
                            print(observation)

                        # Update cycle span with the observation result
                        await cycle_span.update(output=to_json_str(result))
                    except Exception as e:
                        error = f"Error executing tool {tool_name}: {str(e)}"
                        logger.error(error)
                        error_result = {"error": error}

                        # Update root span with the error directly
                        try:
                            await root_span.update(output=to_json_str(error_result))
                        except Exception as e:
                            logger.error(f"Error updating root span: {e}")

                        return error_result

                    # Update context with observation
                    context["last_observation"] = observation
                    context["intermediate_results"][f"step_{current_step}"] = result

        # If we reach here, we hit the maximum steps
        error = f"Reached maximum number of steps ({self.max_steps})"
        logger.warning(error)
        error_result = {"error": error}

        # Update root span with the error output directly
        try:
            await root_span.update(output=to_json_str(error_result))
        except Exception as e:
            logger.error(f"Error updating root span: {e}")

        return error_result

    async def _react_reasoning(
        self, agent: Dict[str, Any], context: Dict[str, Any]
    ) -> AgentReasoning:
        """Generate reasoning based on the current context."""
        # Static instructions for the reasoning step in the ReAct pattern
        reasoning_instructions = """
        You are in the REASONING phase of a ReAct (Reasoning-Acting-Observation) loop.
        
        In this phase, you should:
        1. Analyze the current state and context
        2. Think step-by-step about what you know and what you need to find out
        3. Consider what tools or actions might be helpful
        4. Determine your next steps
        
        Your reasoning should be thorough, logical, and clear. It will be used to decide 
        what action to take next in the ReAct loop.
        
        Additionally, you should provide a confidence score from 0.0 to 1.0 indicating how
        confident you are in your reasoning:
        - 0.0-0.3: Low confidence - you have very limited information and high uncertainty
        - 0.4-0.7: Medium confidence - you have some information but still have uncertainties
        - 0.8-1.0: High confidence - you have sufficient information to make a well-informed decision
        
        This confidence score helps track the quality of the decision-making process.
        """

        # Include the agent's task-specific instructions in the input data
        result, _ = await opper.call(
            name="agent_reasoning",
            instructions=reasoning_instructions,
            input={
                "agent_instructions": agent.get("instructions", ""),
                "context": context,
                "step_number": context.get("current_step", 0),
                "last_observation": context.get("last_observation", None),
            },
            output_type=AgentReasoning,
        )
        return result

    async def _react_action_selection(
        self, agent: Dict[str, Any], context: Dict[str, Any], reasoning: AgentReasoning
    ) -> AgentAction:
        """Select the next action based on reasoning."""
        # Get the list of available tools
        available_tools = list(self.tools.keys())

        # Static instructions for the action selection step in the ReAct pattern
        action_instructions = """
        You are in the ACTION SELECTION phase of a ReAct (Reasoning-Acting-Observation) loop.
        
        Based on your prior reasoning, you must now decide on the next action to take.
        
        You have two options:
        1. Use a tool to gather more information or make progress:
           - action_type: "use_tool"
           - tool_name: Select from the available tools in the input
           - tool_params: Provide the necessary parameters for the tool
           
        2. Finish the task if you have enough information:
           - action_type: "finish"
           - output: Provide your final review with:
             - review_summary: A concise summary of the PR changes
             - issues_found: A list of issues or concerns
             - suggestions: A list of improvement suggestions
             - overall_assessment: Your final assessment of the PR
        
        Choose your action carefully based on your reasoning and the current context.
        """

        # Put the available tools and agent instructions in the input data
        result, _ = await opper.call(
            name="agent_action",
            instructions=action_instructions,
            input={
                "reasoning": reasoning.content,
                "reasoning_confidence": reasoning.confidence,
                "context": context,
                "available_tools": available_tools,
                "agent_instructions": agent.get("instructions", ""),
                "step_number": context.get("current_step", 0),
            },
            output_type=AgentAction,
        )
        return result
