"""
Freelance Services Strategy - Complete tasks for pay
"""

import random
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic import Anthropic

# Task types the agent can handle
TASK_TYPES = {
    "code_review": {
        "description": "Review code for bugs, improvements, and best practices",
        "base_reward": 5.00,
        "difficulty": "medium"
    },
    "write_code": {
        "description": "Write code based on specifications",
        "base_reward": 10.00,
        "difficulty": "hard"
    },
    "explain_concept": {
        "description": "Explain a technical concept clearly",
        "base_reward": 2.00,
        "difficulty": "easy"
    },
    "summarize": {
        "description": "Summarize a document or article",
        "base_reward": 1.50,
        "difficulty": "easy"
    },
    "research": {
        "description": "Research a topic and provide findings",
        "base_reward": 4.00,
        "difficulty": "medium"
    },
    "write_documentation": {
        "description": "Write technical documentation",
        "base_reward": 6.00,
        "difficulty": "medium"
    },
    "debug": {
        "description": "Find and fix bugs in code",
        "base_reward": 8.00,
        "difficulty": "hard"
    },
    "data_analysis": {
        "description": "Analyze data and provide insights",
        "base_reward": 7.00,
        "difficulty": "hard"
    }
}


class FreelanceStrategy:
    """
    Freelance services strategy for AURA.
    Completes tasks submitted via API and earns rewards.
    """
    
    def __init__(self, claude_client: Optional["Anthropic"] = None, demo_mode: bool = True):
        self.client = claude_client
        self.demo_mode = demo_mode
        self.name = "freelance_services"
    
    def get_task_types(self) -> Dict[str, Dict]:
        """Get available task types"""
        return TASK_TYPES
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a submitted task"""
        task_type = task.get("task_type", "explain_concept")
        title = task.get("title", "Untitled Task")
        description = task.get("description", "")
        reward = task.get("reward_usd", TASK_TYPES.get(task_type, {}).get("base_reward", 2.00))
        
        # Build prompt based on task type
        prompt = self._build_prompt(task_type, title, description)
        
        if self.client and not self.demo_mode:
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=3000,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                result = response.content[0].text
                return {
                    "success": True,
                    "task_id": task.get("id"),
                    "result": result,
                    "reward": reward,
                    "completed_at": datetime.now().isoformat()
                }
            except Exception as e:
                return {
                    "success": False,
                    "task_id": task.get("id"),
                    "error": str(e)
                }
        else:
            # Demo mode
            result = self._generate_demo_result(task_type, title, description)
            return {
                "success": True,
                "task_id": task.get("id"),
                "result": result,
                "reward": reward,
                "completed_at": datetime.now().isoformat(),
                "demo": True
            }
    
    def _build_prompt(self, task_type: str, title: str, description: str) -> str:
        """Build a prompt for the task"""
        prompts = {
            "code_review": f"""Please review the following code and provide:
1. Identified bugs or issues
2. Security concerns
3. Performance improvements
4. Best practices suggestions
5. Overall assessment

Task: {title}
Description: {description}""",

            "write_code": f"""Write clean, well-documented code for:

Task: {title}
Requirements: {description}

Please include:
- Working code
- Comments explaining the logic
- Any necessary imports
- Usage example""",

            "explain_concept": f"""Explain the following concept clearly and thoroughly:

Topic: {title}
Context: {description}

Make it accessible to someone learning, but accurate enough for experts.""",

            "summarize": f"""Summarize the following content:

Title: {title}
Content: {description}

Provide:
- Key points
- Main takeaways
- Brief summary (2-3 paragraphs)""",

            "research": f"""Research the following topic:

Topic: {title}
Focus areas: {description}

Provide:
- Overview
- Key findings
- Important considerations
- Recommendations""",

            "write_documentation": f"""Write technical documentation for:

Subject: {title}
Details: {description}

Include:
- Overview
- Installation/Setup (if applicable)
- Usage guide
- API reference (if applicable)
- Examples
- Troubleshooting""",

            "debug": f"""Debug the following issue:

Problem: {title}
Details: {description}

Provide:
- Root cause analysis
- Step-by-step fix
- Prevention tips""",

            "data_analysis": f"""Analyze the following data/scenario:

Context: {title}
Data/Details: {description}

Provide:
- Key insights
- Patterns observed
- Recommendations
- Visualisation suggestions"""
        }
        
        return prompts.get(task_type, f"Complete this task:\n\nTitle: {title}\nDescription: {description}")
    
    def _generate_demo_result(self, task_type: str, title: str, description: str) -> str:
        """Generate demo results without API"""
        if task_type == "code_review":
            return f"""## Code Review: {title}

### Summary
I've reviewed the code and identified several areas for improvement.

### Issues Found
1. **Potential Bug**: Line 42 - Missing null check could cause runtime error
2. **Performance**: The loop at line 78 could be optimized using list comprehension
3. **Security**: User input at line 23 should be sanitized

### Recommendations
- Add input validation
- Implement error handling
- Consider adding unit tests
- Use consistent naming conventions

### Overall Assessment
The code is functional but needs improvements in error handling and security. Rating: 7/10"""

        elif task_type == "write_code":
            return f"""## Solution: {title}

```python
def solve_{title.lower().replace(' ', '_')}():
    \"\"\"
    Solution for: {description[:100]}...
    
    This is a demo implementation.
    \"\"\"
    # Implementation would go here
    result = process_input()
    return result

# Example usage:
# output = solve_{title.lower().replace(' ', '_')}()
```

### Notes
- This is optimized for readability
- Time complexity: O(n)
- Space complexity: O(1)"""

        elif task_type == "explain_concept":
            return f"""## Understanding {title}

### What is it?
{title} is a fundamental concept that helps us understand how things work in this domain.

### Key Points
1. **Core Principle**: The main idea behind {title}
2. **How it Works**: Step-by-step explanation
3. **Why it Matters**: Real-world applications

### Example
Think of it like this: [analogy that makes the concept relatable]

### Summary
{title} is essential for {description[:50]}. Master this and you'll have a solid foundation."""

        else:
            return f"""## Task Completed: {title}

### Overview
Successfully completed the requested task regarding {description[:100]}

### Key Findings
- Finding 1: Important insight
- Finding 2: Key observation
- Finding 3: Notable pattern

### Recommendations
Based on my analysis, I recommend the following next steps...

### Conclusion
The task has been completed successfully. Please review the results and let me know if you need any clarifications."""

    async def execute(self, pending_tasks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the freelance strategy"""
        if not pending_tasks:
            # No tasks - generate a demo task in demo mode
            if self.demo_mode:
                # Simulate picking up a task from the marketplace
                task_type = random.choice(list(TASK_TYPES.keys()))
                demo_task = {
                    "id": f"demo_{int(datetime.now().timestamp())}",
                    "title": f"Demo {task_type.replace('_', ' ').title()} Task",
                    "description": f"This is a simulated {task_type} task to demonstrate the agent's capabilities.",
                    "task_type": task_type,
                    "reward_usd": TASK_TYPES[task_type]["base_reward"]
                }
                pending_tasks = [demo_task]
            else:
                return {
                    "success": True,
                    "strategy": self.name,
                    "action": "no_tasks",
                    "revenue": 0.0,
                    "reasoning": "No pending tasks in queue"
                }
        
        # Process the highest reward task
        task = max(pending_tasks, key=lambda t: t.get("reward_usd", 0))
        result = await self.process_task(task)
        
        if result["success"]:
            return {
                "success": True,
                "strategy": self.name,
                "action": "task_completed",
                "task_id": task.get("id"),
                "task_title": task.get("title"),
                "task_type": task.get("task_type"),
                "result": result["result"],
                "revenue": result["reward"],
                "reasoning": f"Completed {task.get('task_type')} task: '{task.get('title')}' for ${result['reward']:.2f}"
            }
        else:
            return {
                "success": False,
                "strategy": self.name,
                "error": result.get("error", "Task processing failed"),
                "revenue": 0.0
            }
