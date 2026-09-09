"""Build the documented starter shapes, validate with Rasa, kill a lint mutant."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from rasa.mantle.validation import collect_project_findings

root=Path.cwd()
text=(root/'starter-pack/.claude/skills/mantle-new-project/SKILL.md').read_text()
with tempfile.TemporaryDirectory() as tmp:
    project=Path(tmp)
    # Extract the actual documented agent/integration/memory blocks, not copies.
    for heading,filename in [('3. agent.yml','agent.yml'),('4. integrations.yml','integrations.yml'),('5. memory.yml','memory.yml')]:
        section=text.split('## '+heading,1)[1].split('\n## ',1)[0]
        value=re.search(r'```yaml\n(.*?)\n```',section,re.S).group(1)
        value=value.replace('<AgentName>','Juniper').replace('<domain>','fictional plant shop')
        (project/filename).write_text(value+'\n')
    skill=project/'skills/default_session_start';skill.mkdir(parents=True)
    (skill/'skill.md').write_text('---\nname: default_session_start\ndescription: Greet a learner.\n---\nWelcome the learner to the fictional plant shop.\n')
    findings=collect_project_findings(project)
    assert not findings, findings
    lint=root/'starter-pack/scripts/lint_mantle.py'
    command=[sys.executable,str(lint),'--check','project-memory-writes']
    baseline=subprocess.run(command,cwd=project,text=True,capture_output=True)
    assert baseline.returncode==0, baseline.stdout+baseline.stderr
    (project/'memory.yml').write_text('customer_id:\n  type: text\n  llm_settable: true\n')
    result=subprocess.run(command,cwd=project,text=True,capture_output=True)
    assert result.returncode!=0 and 'project-memory-writes' in result.stdout, result.stdout+result.stderr
print('Documented starter YAML validates; model-writable project memory fails lint')
