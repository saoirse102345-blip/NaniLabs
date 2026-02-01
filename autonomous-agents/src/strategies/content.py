"""
Content Creation Strategy - Generate monetizable content
"""

import random
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic import Anthropic

# Content topics and niches that tend to perform well
TRENDING_NICHES = [
    "AI and automation",
    "Personal finance tips",
    "Productivity hacks",
    "Tech tutorials",
    "Crypto/blockchain basics",
    "Remote work strategies",
    "Side hustle ideas",
    "Health and wellness tech",
    "Programming tips",
    "Career development"
]

CONTENT_TYPES = [
    {"type": "tweet_thread", "platform": "twitter", "base_revenue": 0.50, "time_minutes": 5},
    {"type": "blog_post", "platform": "medium", "base_revenue": 2.00, "time_minutes": 15},
    {"type": "linkedin_post", "platform": "linkedin", "base_revenue": 1.00, "time_minutes": 8},
    {"type": "newsletter", "platform": "substack", "base_revenue": 3.00, "time_minutes": 20},
    {"type": "tutorial", "platform": "dev.to", "base_revenue": 2.50, "time_minutes": 25},
]


class ContentStrategy:
    """
    Content creation strategy for AURA.
    Generates blog posts, tweets, articles using Claude.
    """
    
    def __init__(self, claude_client: Optional["Anthropic"] = None, demo_mode: bool = True):
        self.client = claude_client
        self.demo_mode = demo_mode
        self.name = "content_creation"
    
    async def select_topic(self) -> Dict[str, Any]:
        """Select a trending topic to write about"""
        niche = random.choice(TRENDING_NICHES)
        content_type = random.choice(CONTENT_TYPES)
        
        # In real mode, would analyze trends
        topic_ideas = {
            "AI and automation": [
                "5 Ways AI is Changing How We Work in 2025",
                "Automate Your Boring Tasks: A Beginner's Guide",
                "The Future of AI Agents: What You Need to Know"
            ],
            "Personal finance tips": [
                "How to Build an Emergency Fund in 90 Days",
                "The 50/30/20 Budget Rule Explained Simply",
                "Passive Income Ideas That Actually Work"
            ],
            "Productivity hacks": [
                "The 2-Minute Rule That Changed My Life",
                "Why Multitasking is Killing Your Productivity",
                "Morning Routines of Successful People"
            ],
            "Tech tutorials": [
                "Getting Started with Python in 2025",
                "Build Your First API in 30 Minutes",
                "Docker for Beginners: A Practical Guide"
            ],
            "Programming tips": [
                "10 VS Code Extensions Every Developer Needs",
                "Git Commands You Should Know",
                "Clean Code Principles That Will Level Up Your Skills"
            ]
        }
        
        topics = topic_ideas.get(niche, [f"Essential Guide to {niche}"])
        
        return {
            "niche": niche,
            "topic": random.choice(topics),
            "content_type": content_type["type"],
            "platform": content_type["platform"],
            "estimated_revenue": content_type["base_revenue"],
            "estimated_time_minutes": content_type["time_minutes"]
        }
    
    async def generate_content(self, topic: str, content_type: str) -> Dict[str, Any]:
        """Generate content using Claude"""
        
        prompts = {
            "tweet_thread": f"""Write a compelling Twitter thread (5-7 tweets) about: {topic}

Make it engaging, informative, and shareable. Use emojis sparingly.
Format as Tweet 1:, Tweet 2:, etc.
End with a call to action.""",

            "blog_post": f"""Write a blog post about: {topic}

Structure:
- Catchy title
- Hook introduction (2-3 sentences)
- 3-5 main points with explanations
- Practical examples or tips
- Conclusion with call to action

Keep it around 800-1000 words. Make it valuable and actionable.""",

            "linkedin_post": f"""Write a LinkedIn post about: {topic}

Make it professional but personable. Use short paragraphs.
Include a hook at the start.
End with a question to drive engagement.
Around 200-300 words.""",

            "newsletter": f"""Write a newsletter issue about: {topic}

Include:
- Subject line
- Greeting
- Main insight/lesson
- 3 actionable tips
- Resource recommendation
- Sign-off

Make it feel personal and valuable.""",

            "tutorial": f"""Write a technical tutorial about: {topic}

Include:
- Clear title
- Prerequisites
- Step-by-step instructions
- Code examples (if applicable)
- Common pitfalls to avoid
- Next steps

Make it beginner-friendly but thorough."""
        }
        
        prompt = prompts.get(content_type, prompts["blog_post"])
        
        if self.client and not self.demo_mode:
            # Real Claude API call
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                content = response.content[0].text
                return {
                    "success": True,
                    "title": topic,
                    "body": content,
                    "content_type": content_type,
                    "generated_at": datetime.now().isoformat()
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # Demo mode - generate placeholder
            demo_content = self._generate_demo_content(topic, content_type)
            return {
                "success": True,
                "title": topic,
                "body": demo_content,
                "content_type": content_type,
                "generated_at": datetime.now().isoformat(),
                "demo": True
            }
    
    def _generate_demo_content(self, topic: str, content_type: str) -> str:
        """Generate demo content without API"""
        if content_type == "tweet_thread":
            return f"""Tweet 1: 🧵 Let me share what I've learned about {topic}...

Tweet 2: First, the basics. Understanding the fundamentals is key to mastering any skill.

Tweet 3: Here's the game-changer most people miss: consistency beats intensity every time.

Tweet 4: Pro tip: Start small, iterate fast, and don't be afraid to fail.

Tweet 5: The best time to start was yesterday. The second best time is NOW.

Tweet 6: If this helped, follow for more insights on {topic}! 🚀"""

        elif content_type == "blog_post":
            return f"""# {topic}

## Introduction
In today's fast-paced world, understanding {topic.lower()} has become essential. Let me share the key insights that will help you get ahead.

## Why This Matters
Most people overlook the fundamentals. But mastering the basics is what separates beginners from experts.

## Key Takeaways

### 1. Start With Why
Before diving into the how, understand the why. This gives you direction and motivation.

### 2. Build Systems, Not Goals
Goals are good for setting direction. Systems are what actually get you there.

### 3. Iterate and Improve
Don't wait for perfection. Ship early, get feedback, and improve.

## Conclusion
The journey of a thousand miles begins with a single step. Start today, stay consistent, and watch the compound effects unfold.

---
*Found this helpful? Share it with someone who needs to hear this.*"""

        elif content_type == "linkedin_post":
            return f"""I've been thinking about {topic} a lot lately.

Here's what I've realized:

Success isn't about having all the answers.
It's about asking the right questions.

Three things that changed my perspective:

1️⃣ Progress over perfection
2️⃣ Learning over knowing
3️⃣ Action over planning

The best investment you can make is in yourself.

What's one thing you're working on improving right now?

#Growth #Learning #{topic.replace(' ', '')}"""

        else:
            return f"""# {topic}

[Demo content generated for {content_type}]

This is placeholder content demonstrating the agent's capability to generate monetizable content.

In production mode, this would be fully AI-generated, high-quality content tailored to the target platform and audience."""

    async def execute(self) -> Dict[str, Any]:
        """Execute the content creation strategy"""
        # 1. Select topic
        topic_info = await self.select_topic()
        
        # 2. Generate content
        content = await self.generate_content(
            topic_info["topic"], 
            topic_info["content_type"]
        )
        
        if not content["success"]:
            return {
                "success": False,
                "strategy": self.name,
                "error": content.get("error", "Content generation failed"),
                "revenue": 0.0
            }
        
        # 3. Calculate simulated revenue (in demo mode)
        # Real revenue would come from actual monetization
        base_revenue = topic_info["estimated_revenue"]
        quality_multiplier = random.uniform(0.8, 1.5)
        revenue = round(base_revenue * quality_multiplier, 2)
        
        return {
            "success": True,
            "strategy": self.name,
            "action": "content_created",
            "topic": topic_info["topic"],
            "content_type": topic_info["content_type"],
            "platform": topic_info["platform"],
            "content": content,
            "revenue": revenue,
            "reasoning": f"Generated {topic_info['content_type']} about '{topic_info['topic']}' for {topic_info['platform']}"
        }
