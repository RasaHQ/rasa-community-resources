"""Open/update only an automation-owned candidate branch after gates succeed."""
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile

root=Path.cwd()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
version=(root/'RASA_PRO_VERSION').read_text().strip()
if not re.fullmatch(r'[0-9][0-9a-z.]*',version):raise SystemExit('Invalid branch version')
previous=git('show','origin/main:RASA_PRO_VERSION').strip()
if version==previous:
    print('Daily checks passed on the adopted release; evidence is retained as a workflow artifact.')
    raise SystemExit(0)
branch='automation/rasa-'+version
# Explicit files plus already tracked changes. Never stage secrets or build outputs.
subprocess.run(['git','add','-u'],check=True)
subprocess.run(['git','add','RASA_RELEASE.json','COMPATIBILITY.json'],check=True)
subprocess.run(['git','config','user.name','github-actions[bot]'],check=True)
subprocess.run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],check=True)
subprocess.run(['git','checkout','-B',branch],check=True)
subprocess.run(['git','commit','-m',f'Adopt tested Rasa Pro {version}'],check=True)
subprocess.run(['git','push','--force-with-lease','origin',f'HEAD:refs/heads/{branch}'],check=True)
repo=os.environ['GITHUB_REPOSITORY']
run=f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
body=f'''Updates the maintained Rasa pin from {previous} to {version} after the daily workflow downloaded and SHA-256-verified the PyPI wheel, checked the required engine, and executed compatibility gates.

The committed COMPATIBILITY.json records exact scope, source hashes and test results. Passing deterministic fixtures does not establish every live conversation or external integration. Draft publication flags and audience judgments are unchanged.

Validation: [complete workflow and downloadable evidence]({run}). Checks ran before this PR was proposed; they do not depend on a token-created PR triggering another workflow. Human review and merge are required. No automatic deployment approval is granted by this job.
'''
with tempfile.NamedTemporaryFile(mode='w',suffix='.md') as file:
    file.write(body);file.flush()
    prs=json.loads(subprocess.check_output(['gh','pr','list','--repo',repo,'--head',branch,'--state','open','--json','number'],text=True))
    if prs:command=['gh','pr','edit',str(prs[0]['number']),'--repo',repo,'--title',f'Adopt tested Rasa Pro {version}','--body-file',file.name]
    else:command=['gh','pr','create','--repo',repo,'--base','main','--head',branch,'--title',f'Adopt tested Rasa Pro {version}','--body-file',file.name]
    subprocess.run(command,check=True)
