# ReAct Agent Examples

This directory contains working code examples for the "Building Intelligent Agents with ReAct" blog series. Each subdirectory corresponds to a specific blog post and contains a fully functional implementation of the concepts discussed in that post.

## Directory Structure

- **[01-github-pr-reviewer](01-github-pr-reviewer)**: Example code for the first blog post, implementing a simple GitHub PR review agent using the ReAct pattern.

## Running the Examples

Each example directory contains:

1. A README with specific instructions
2. All necessary source code
3. A requirements.txt file listing dependencies
4. Example configuration files

To run any example, follow these general steps:

1. Navigate to the example directory:
   ```bash
   cd 01-github-pr-reviewer
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the necessary environment variables or configuration files as specified in the example's README.

5. Run the example according to its specific instructions.

## Example Code Structure

All examples follow consistent patterns, making it easier to understand how concepts build on each other throughout the series:

- Schema-driven design with Pydantic models
- ReAct pattern implementation
- Opper tracing for observability
- Async/await for efficient execution
- Modular tools architecture
- Error handling and validation

The examples are designed to be both educational and practical - you can use them as a reference for building your own agents or modify them for your specific use cases.