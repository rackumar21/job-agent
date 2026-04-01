Run a full test of the Job Agent dashboard. Check each item and report pass/fail.

## Tests to run:

### 1. Servers running
- Check local API: `curl -s http://localhost:8001/api/health` — should return `{"status":"ok"}`
- Check Render API: `curl -s https://job-agent-2h5u.onrender.com/api/health` — should return `{"status":"ok"}`
- If local API is down, restart it: `source venv/bin/activate && nohup python3 -m uvicorn api.main:app --port 8001 --reload > /tmp/api.log 2>&1 &`

### 2. Render deployment is current
- Get latest committed JS bundle: `ls frontend/dist/assets/*.js | xargs basename`
- Get Render's bundle: `curl -s https://job-agent-2h5u.onrender.com/ | grep -o 'index-[^"]*\.js'`
- If different, tell user to deploy on Render: Manual Deploy → Deploy latest commit

### 3. Git is clean
- Run `git status --short` — should be empty or only untracked files
- If there are uncommitted changes in frontend/src or agent/, warn the user

### 4. API endpoints work
- Extract post: `curl -s -X POST http://localhost:8001/api/sources/extract-post -H "Content-Type: application/json" -d '{"text":"TestCompanyXYZ"}'` — should return JSON with companies_found
- Health: already checked above
- If extract-post returns 401 authentication error, the ANTHROPIC_API_KEY is wrong

### 5. Data integrity
Run this Python check:
```python
source venv/bin/activate && python3 -c "
from supabase import create_client; from dotenv import load_dotenv; import os
load_dotenv()
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

# Count by status
for s in ['prep_ready','borderline','new','pipeline','applied','skip']:
    r = sb.table('jobs').select('id', count='exact').eq('status', s).execute()
    print(f'  {s}: {r.count}')

# Jobs missing company_id
r = sb.table('jobs').select('id,company_name',count='exact').is_('company_id','null').in_('status',['prep_ready','borderline']).execute()
print(f'Open roles missing company_id: {r.count}')
if r.data:
    for j in r.data[:5]: print(f'  {j[\"company_name\"]}')

# Companies missing description
r = sb.table('companies').select('name',count='exact').is_('what_they_do','null').not_.is_('attention_score','null').execute()
print(f'Companies missing description: {r.count}')
if r.data:
    for c in r.data[:5]: print(f'  {c[\"name\"]}')
"
```

### 6. UI checks (tell user to verify visually)
Report these for the user to check on localhost:3001:
- [ ] Open Roles: cards show description, sector, stage
- [ ] Open Roles: buttons say "Pipeline / Outreach / Applied" (one line each)
- [ ] Open Roles: no "Refresh" button
- [ ] Open Roles: skip form is gray (not red)
- [ ] Header: no stat pills (68 open, 33 radar, etc.)
- [ ] Header: tab says "Outreach" not "Reached Out"
- [ ] Header: logo is ⚡
- [ ] On Radar: count shows below filters (not inline on right)
- [ ] Sources: "How this agent works" has no stats bar at bottom
- [ ] Sources: all sections in cards (consistent font)

### Summary
Print a summary table of all checks: PASS / FAIL / WARN for each.
If any FAIL, explain what to do to fix it.
