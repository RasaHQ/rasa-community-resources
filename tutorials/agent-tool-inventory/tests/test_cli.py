import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

D = Path(__file__).resolve().parents[1]

class CliControls(unittest.TestCase):
    def call(self, *args):
        return subprocess.run([sys.executable, '-B', str(D/'inventory_cli.py'), *map(str,args)], capture_output=True, text=True, env=os.environ.copy(), timeout=30)

    def test_help_explains_execution(self):
        r=self.call('--help');self.assertEqual(r.returncode,0);self.assertIn('executes',r.stdout)

    def test_requires_trusted_project_acknowledgement(self):
        r=self.call('snapshot',D);self.assertEqual(r.returncode,2);self.assertEqual(r.stdout,'')

    def test_requires_expected_for_check(self):
        r=self.call('check',D,'--trusted-python');self.assertEqual(r.returncode,2)

    def test_rejects_expected_for_snapshot(self):
        r=self.call('snapshot',D,'--trusted-python','--expected','unused');self.assertEqual(r.returncode,2)

    def test_missing_project_refused(self):
        r=self.call('snapshot',D/'absent','--trusted-python');self.assertEqual(r.returncode,1);self.assertEqual(json.loads(r.stdout)['status'],'refused')

    def test_snapshot_and_check_and_drift(self):
        r=self.call('snapshot',D,'--trusted-python');self.assertEqual(r.returncode,0,r.stderr)
        actual=json.loads(r.stdout);self.assertEqual(actual['unresolved'],[])
        with tempfile.TemporaryDirectory(dir=D) as temp:
            p=Path(temp)/'reviewed.json';p.write_text(json.dumps(actual))
            good=self.call('check',D,'--trusted-python','--expected',p)
            self.assertEqual(good.returncode,0,good.stderr);self.assertEqual(json.loads(good.stdout)['status'],'match')
            actual['rows'][0]['sourceSha256']='0'*64;p.write_text(json.dumps(actual))
            bad=self.call('check',D,'--trusted-python','--expected',p)
            self.assertEqual(bad.returncode,1);self.assertEqual(json.loads(bad.stdout)['status'],'refused');self.assertIn('differs',json.loads(bad.stdout)['reason'])

    def test_new_local_tool_requires_a_new_reviewed_snapshot(self):
        baseline = self.call('snapshot', D, '--trusted-python')
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        local = D / 'skills/review_record/tools.py'
        original = local.read_text()
        addition = '\n@tool(description="Read an invented revision.")\nasync def read_revision(context: ToolContext) -> ToolResult:\n    return ToolResult(llm_response={"revision": 1})\n'
        with tempfile.TemporaryDirectory(dir=D) as temporary:
            expected = Path(temporary) / 'reviewed.json'
            expected.write_text(baseline.stdout)
            try:
                local.write_text(original + addition)
                changed = self.call('snapshot', D, '--trusted-python')
                self.assertEqual(changed.returncode, 0, changed.stderr)
                tools = {row['tool'] for row in json.loads(changed.stdout)['rows']}
                self.assertIn('read_revision', tools)
                comparison = self.call('check', D, '--trusted-python', '--expected', expected)
                self.assertEqual(comparison.returncode, 1, comparison.stderr)
                self.assertEqual(json.loads(comparison.stdout)['status'], 'refused')
            finally:
                local.write_text(original)

    def test_declared_unbound_tool_cannot_be_saved_as_snapshot(self):
        skill=D/'skills/review_record/skill.md'
        original=skill.read_text()
        try:
            skill.write_text(original.replace('  - record_review\n','  - record_review\n  - missing_tool\n',1))
            result=self.call('snapshot',D,'--trusted-python')
            self.assertEqual(result.returncode,1,result.stderr)
            report=json.loads(result.stdout)
            self.assertEqual(report['status'],'refused')
            self.assertIn('without loaded Python bindings',report['reason'])
        finally:
            skill.write_text(original)

    def test_invalid_expected_json_refused(self):
        with tempfile.TemporaryDirectory(dir=D) as temp:
            p=Path(temp)/'invalid.json';p.write_text('{')
            r=self.call('check',D,'--trusted-python','--expected',p)
            self.assertEqual(r.returncode,1);self.assertEqual(json.loads(r.stdout)['status'],'refused')

if __name__ == '__main__':
    unittest.main()
