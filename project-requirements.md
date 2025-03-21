Superego Agent Project Requirements - MVP version. 

A Langgraph project that contains a StateGraph-powered multi-agent flow. It is interacted with simply via the Python terminal when a user message is required, then the flow begins. 

Here is the intended behaviour: 

1. The user runs the Python program and is prompted for an input. 
2. The user sends an initial prompt, such as 'Hi, please can you tell me where to buy eggs?' in the Python CLI. 
3. The user request is first sent to an input_superego agent, which is a standard reAct agent. Its conversation history is: 
  - The 'system' message is made of two components which are concatenated:
    - INSTRUCTIONS (by default, data/agent_instructions/input_superego.md)
    - CONSTITUTION (by default, data/constitutions/default.md)
  - The previous rest of the conversational context - most of the time this will just be the previous message. 
4. The superego agents textual output is STREAMED to the user's console. 
5. The superego agent has access to two tools - ALLOW, which accepts the user input, or BLOCK which blocks the user input. It uses one of the two tools. 
6. If 'ALLOW' tool is used, the conversation continues, handing off to the inner_agent. 
7. By default, the inner_agent is just a regular reAct agent also, with its 'system' message found in agent_instructions/inner_agent_default.md
8. The inner_agent can take any of the default actions that an inner_agent is able to take in the langgraph framework. Later this may be a subgraph. 
9. The inner_agent's output is STREAMED to the user's console. 
10. The inner_agent can call tools and itself cyclically, but when it is finally done, the flow is complete and the user can provide another input to start the process again. 


A note on extensibility: 
- The following features are planned for the future, so keep them in mind. However the functionality is not necessary immediately: 
  - The ability to CRUD the constitutions and system instructions and select them before running the app. 
  - The ability to rerun the flow from a certain point, changing a variable such as the superego's constitution
  - Future support for streaming the inner_agents outputs through a second superego LLM, which screens outputs for harm and can block the model's outputs. 
  - Having the 'inner_agent' be a definable/pluggable subgraph of other agents instead of just one inner_agent