Run ATS analysis on a resume against a job description.

## Input: $ARGUMENTS

The user will provide two things:
1. **Resume** — a file path (PDF, .docx, or .md), or pasted resume text
2. **Job** — a URL (Ashby, Greenhouse, Lever, Workable, any career page) or pasted JD text

## Steps

### 1. Read the resume

- If a file path is given: read it (PDF, .docx, .md, or .txt)
- If text is pasted: use it directly
- If neither is provided: ask the user for their resume

### 2. Get the job description

If a URL is given (starts with http):
- Fetch the page using WebFetch and extract the job title, company, and JD text
- For Ashby URLs: use the API `https://api.ashbyhq.com/posting-api/job-board/{slug}`
- For Greenhouse URLs: use `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{id}`
- For other URLs: fetch the page, strip HTML tags, extract the job description text

If raw JD text is given:
- Ask for the job title and company name if not obvious from the text

If neither is provided: ask the user for the job link or JD text

### 3. Run ATS analysis

Act as a senior recruiter AND ATS system. Evaluate the resume against the JD.

Analyze:
- **ATS Score (0-100):** How well the resume matches this JD
- **Summary:** 2-3 sentence overall assessment
- **Strong Matches:** Up to 3 resume bullets that directly address JD requirements
- **Gaps:** Up to 4 gaps with severity (HIGH/MEDIUM/LOW) and specific fix recommendations
- **Missing Keywords:** Important JD terms not in the resume
- **Rewrite Suggestions:** Exactly 3 highest-impact bullet rewrites. CRITICAL RULES:
  - Each rewrite must be the SAME LENGTH OR SHORTER than the original (character count)
  - Each rewrite must only modify that single bullet, never merge bullets
  - Never use em dashes, en dashes, or arrows
- **Cover Letter Angles:** 2-3 specific angles to highlight

### 4. Present results clearly

Show the results in this format:

**ATS Score: XX/100**

**Summary:** (the summary)

**Strong Matches:**
- (list each)

**Gaps:**
- [HIGH/MEDIUM/LOW] gap — recommendation

**Missing Keywords:** keyword1, keyword2, keyword3

**Suggested Rewrites:**
For each rewrite:
> **ORIGINAL:** the original bullet
> **REWRITE:** the rewritten version
> **WHY:** the reason

**Cover Letter Angles:**
- (list each)

### 5. Offer next steps

Ask: "Want me to open the Resume tab to review these interactively? http://localhost:3002/resume"
