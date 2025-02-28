# Engineering Exercise: Life Narrative Explorer

## Background
Modern photo libraries are vast but lack meaningful organization. We think AI can be used to surface the hidden stories in your photos—like "adventures in the mountains," "family milestones," or "creative projects"—and let you experience them as visual narratives. 

## Objective
Develop a rough prototype of an app that analyzes collections of thousands of your own photos to generate AI-curated "life narratives". Your app will let the user view different narratives in their life along with the photos that belong to them. 

Your prototype will demonstrate how AI can transform passive photo storage into engaging storytelling.

## Core Approach to Implement

### Input
Use any sequence of thousands of photos from your library. A full product would analyze an entire gallery (often 100K photos), but for this exercise, keep it simpler. Try your code on different time periods from your photo library (each with a few thousand photos) to test its performance in different scenarios.

### Step 1 – Photo Analysis
Use an LLM to generate a short text description for each photo, focusing on key details (e.g., people, activities, locations, emotions, anything else you think would help).

### Step 2 – Narrative Generation
Use another LLM to analyze all descriptions and group them into "life narratives." Allow the LLM to define the themes and scope of each narrative as it sees fit – you are passing judgement to an LLM on what an interesting "life story" is for this person, and which photos belong to which narrative.

### Step 3 – Final Photo Selection for Narratives
If you showed the user every photo linked to a narrative, the feed would be boring—full of similar or uninteresting images. Design and implement any method to select the final photos a user will see when viewing each life narrative.

### Step 4 – User Interface
Build a simple UI to view these photo narratives. There should be some way to see all of my life narratives, choose which one I want to watch, and then some way to click through the photos that belong to each narrative.

### Step 5 – Experience Improvements (Optional)
Add any features you believe will make the overall experience of exploring and viewing life narratives as engaging and memorable as possible.

## Technical Guidelines

- **Use AI-Assisted Coding**: Leverage AI tools to build all parts of this prototype. If you don't have a preferred AI coding stack, try lovable for the front end, cursor for everything else
- **Prioritize Speed Over Perfection**: Skip non-essential features (e.g., authentication, edge cases). Take any shortcuts that feel right and just help you get to a working demo of the core flow.
- **Focus on Your Own Photos**: We recommend building this with your own photos, it's fun and also the only real way to feel if the prototype you're building is any good. 

## What We're Looking For
We'll meet for a demo, during which we'll:
1. Try your prototype on a collection of thousands of our own photos and discuss the results
2. Review your code (please send it ahead of time)

Please also send us a short writeup (≤½ page) explaining your:
- Overall approach
- AI tools used
- Ideas for improvement

This will help us ask interesting questions.

---

**Remember**: The goal is creativity within constraints—use AI relentlessly, cut corners, and focus on the magic of telling great life stories through photos.
