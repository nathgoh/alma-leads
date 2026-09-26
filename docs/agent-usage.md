# Agent Usage
## Tools used
- Codex
- Claude Code
- Opencode + Ollama (using open-sourced models i.e. GLM 5.3, Deepseek, etc.)

## The Code
Using Claude and Codex to help create a system design documentation based on the functional requirements and technical requirements described in the take-home.
Prompt was structured as such: 

```
Help me draft a system design document based on these functional 
and technical requirements: [PASTE REQUIREMENTS]

For handling the storage of data like resumes, I want to use a S3-compatible tool like minio, 
postgres for my DB through the usage of Prisma
```

This was sent through Claude and I reviewed to make any changes before having it reviewed by Codex
- One example being that the initial proposal wanted to use the prisma python client, however I found that this is deprecated and no longer maintained so I followed up 
  - "The prisma python client is deprecated, update the doc to no longer reference that and adjust according by using sqlalchemy as our ORM"
Once this was done I had it reviewed by Codex and made more refinements.

Fixes caught:
 - When going through the UI if you're logged in as an attonery, I found that using the pagination view and purposely setting it to some higher number i.e. /leads?page=999, we would render a "No leads here yet", which no pagination navigation. There's no way back and while technically this isn't exactly a wrong state, it's a bad UI experience that I want to fix. The fix then was to guard to the last "real page" when the page exceeds the count.
 - Testing the UI experience found it was bad that we couldn't switch between logging in as an attorney or submitting an assessment (and vice versa).

