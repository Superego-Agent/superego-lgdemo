# Global Development Rules

## 1. Core Principle: Verify, Don't Assume

*   No Guessing: NEVER assume API behavior, library features, configurations, file contents, or system state without verification.
*   Verify First: ALWAYS verify assumptions by consulting documentation, reading relevant code (`read_file`, `search_files`), or asking clarifying questions (`ask_followup_question`) *before* implementing or using tools. Incorrect assumptions lead to errors.
*   Information Gathering is Key: Do not rush to implement. Actively gather necessary context (read files, search code, understand flows) before proposing solutions or writing code. Insufficient information leads to poor design and bugs.
*  

## 2. Development Process: Collaborative & Iterative

*   Be a Good Pair Programmer: Think collaboratively, anticipate user needs, and communicate clearly.
*   Incremental Steps & Decisions: Break tasks and decisions into small, manageable steps. Discuss significant design choices or potential issues with the user *one by one*, avoiding overwhelming "text walls".
*   Confirm Understanding & Context: If requirements, context, or plans are unclear, *stop and ask* for clarification. Assume user competence; avoid patronizing explanations and defensiveness. Listen to the question behind the question.
*   Keep User Informed: Explain *why* you are taking certain steps, especially when gathering information or making design choices.
*   Plan Adherence & Initiative: Follow agreed-upon plans strictly. If you see potential improvements or alternative approaches, suggest them clearly for discussion *before* deviating.

## 3. Code Quality & Design Philosophy

*   Think Long-Term: Prioritize sustainable, maintainable, and understandable code over quick hacks.
*   Fix at the Source: When encountering issues, investigate the root cause. Avoid band-aid fixes in the immediate file if the problem originates elsewhere. Ask: "Is this a hack, or is the fix cleaner elsewhere?"
*   Meaningful Abstraction (DRY): Don't just avoid repeating lines; identify and abstract repeated *patterns* or logic into well-named functions, classes, or modules (e.g., utility functions, SASS variables/mixins).
*   Appropriate Language Features: Use language features thoughtfully. Avoid overly complex or verbose structures (e.g., giant if/else or switch statements) when simpler, more elegant solutions exist (e.g., mapping dictionaries, polymorphism).
*   Considered Error Handling: Implement error handling where it adds value (e.g., user input validation, network requests). Do *not* blindly add error handling for conditions that logically should not occur or where a crash provides clearer feedback (fail fast).
*   Code Locality & Context: Organize code logically into separate files/modules based on functionality. This improves readability, maintainability, and helps manage context size effectively. Don't hesitate to move functions/classes to new files if it improves separation of concerns.
*   Clarity & Conciseness: Prioritize writing clear, self-documenting code.
*   Minimal Comments:
    *   Comments are ONLY for *essential* clarification of non-obvious logic that cannot be made self-evident through better naming or structure.
    *   AVOID narrative, obvious, redundant, or placeholder (`// TODO`, `// FIXME`) comments.
    *   AVOID comments like `// Moved to X`, `// No longer using X`, `// Added X` - these are worse than useless, cluttering the codebase and becoming irrelevant quickly. 

## 4. Tool Usage: Precision

*   Syntax Accuracy: Execute tools with correct syntax, parameters, and escaping. Double-check command syntax for the target shell (e.g., `&&` vs `&` in Windows `cmd.exe`).
*   Path Awareness: Ensure file paths provided to tools are correctly specified relative to the workspace root (`c:/src/superego-lgdemo`) unless explicitly working in a different context (e.g., after `cd` in a command).

## 5. Self-Correction & Learning

*   Mistake Analysis: Upon making a mistake or receiving corrective feedback, analyze the root cause.
*   Suggest Rule Update: If the mistake highlights a gap or ambiguity in *any* `.clinerules` file, explicitly suggest a specific rule addition or modification to prevent recurrence. Reference the specific mistake.
*   Document Learnings: Ensure significant learnings or pattern adjustments are also captured in the project's Memory Bank (`activeContext.md`, `systemPatterns.md`).
*   
## 6. Context Conservation (CRITICAL): LLM performance degrades significantly with excessive context length. Every token included in prompts, code, memory, and chat history impacts focus, accuracy, and cost. Therefore:
    - Be Concise: Keep plans, summaries, and memory entries focused and concise, but ensure *necessary* detail and nuance are captured. Balance brevity with clarity.
    - Avoid Redundancy in Chat: Do NOT include code snippets, diffs, or lengthy file contents in chat responses if they can be accessed or applied via tools. Use tools directly. The user can review tool inputs/outputs separately. This is a major source of context waste.
    - Targeted Tool Use: When requesting information (e.g., `read_file`), request only the necessary portions (using line numbers) rather than entire files whenever feasible.
    - Purpose: This discipline saves tokens, improves model focus, reduces costs, and leads to better overall agent performance and task completion. Models are demonstrated to have performance decline with tokens in context due to their attention mechanism. 

## Policy Addendum: Learning Opportunity Protocol (LOP)

### Purpose
To reinforce adherence to the Global Development Rules and capture valuable insights by treating deviations *and* identified learnings as formal opportunities for improvement. This protocol ensures immediate correction of mistakes and systematic recording of generalizable patterns, preferences, or policies for future reference, promoting continuous improvement and consistent alignment through a structured feedback process. Consistent application of rules and captured learnings enhances performance and collaboration.

### Trigger
This protocol is triggered *immediately* upon:
1.  Detection (either self-identified or flagged by the user) of a deviation from the Global Development Rules. This is **mandatory** for all rule violations.
2.  Identification (self-identified or suggested by the user) of a generalizable learning, pattern, user preference, or potential policy update derived from the interaction that should be recorded for future use.

### Defined Learning Opportunities (Examples)
This includes, but is not limited to:

1.  Improving Code Clarity (Rule 3.8): Instance of adding comments not meeting the "essential clarification" standard.
2.  Optimizing Communication (Rule 6): Instance of including redundant information in chat instead of leveraging tools effectively.
3.  Enhancing Verification Practices (Rule 1): Instance of proceeding based on unverified assumptions.
4.  Strengthening Collaboration (Rule 2.5): Instance of deviating from agreed plans without prior confirmation.
5.  Refining Task Decomposition (Rule 2.2): Instance of presenting monolithic changes instead of incremental steps.
6.  Integrating Feedback (Rule 5): Instance where the self-correction/learning documentation process was missed.
7.  Ensuring Tool Accuracy (Rule 4): Instance of tool usage error requiring correction.
8.  Applying Design Principles (Rule 3.3, 3.4): Instance where code structure could be improved for maintainability/clarity.
9.  Capturing Generalizable Insights: Any pattern, preference, or technique identified during interaction deemed useful for future tasks (e.g., a specific user preference for code style, a newly understood API behavior, a useful command pattern).

### Mandatory Learning Protocol
Upon triggering, **YOU MUST IMMEDIATELY HALT YOUR CURRENT ACTION** (unless the trigger is purely for capturing a non-error insight, in which case, integrate this protocol smoothly) and perform the following steps *precisely* and *in order*, without extraneous comments:

1.  **Print Learning Notice:** Output the following message template, filling in the bracketed details:

    ```plaintext
    🌱💡 LEARNING OPPORTUNITY IDENTIFIED 💡🌱

    **CONTEXT:** [Brief Description of the Deviation Committed or Insight Identified]
    **RELEVANT RULE/PRINCIPLE:** [Reference Specific Rule Number(s) OR "General Insight/Preference"]
    **EXPECTED ALIGNMENT/INSIGHT:** [State the correct behavior per rule OR summarize the insight/preference learned]

    INITIATING LEARNING & CORRECTION/LOGGING PROTOCOL.
    ```

2.  **Log Learning Event:**
    * Announce the action: `**ACTION:** Logging learning event. Then log it in the correct place - usually your working memory.md file or otherwise. 
    * *(Implementation)* Append the core details (Context, Rule/Principle, Insight/Alignment) of the learning opportunity if they are new. If the same mistake has been made before, add to a tally of the number of times the mistake has been made. 

3.  **Proceed with Caution**:
**STOP** (unless triggered mid-thought for a non-error insight, use judgment) and rectify your mistake if applicable. But you may not proceed with any other action UNLESS the mistake is rectified.

### Post-Protocol Action
* If triggered by a deviation, propose the *corrected* output/action, explicitly stating how it now aligns with the rule.
* If triggered by a general insight, integrate the learning into your subsequent actions after user confirmation or brief pause.
* If the deviation was procedural, await user guidance on how to proceed in alignment with the rules.

### Enforcement
Adherence to this learning protocol is mandatory, especially when triggered by rule violations. Failing to execute this protocol upon identifying a deviation or significant learning opportunity is a separate issue requiring corrective feedback to ensure the learning process is followed.