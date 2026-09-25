# Agent Usage
## Tools used
- Codex
- Claude Code
- Opencode + Ollama (using open-sourced models i.e. GLM 5.3, Deepseek, etc.)

## The drafting
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
