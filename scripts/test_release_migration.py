"""Regress the path-dependency ordering and fail-closed root pin update."""
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
import rasa_projects
from unittest.mock import patch
import migrate_rasa_pro as migration


class MigrationOrderTests(unittest.TestCase):
    def exercise(self, fail=False):
        projects=[SimpleNamespace(path=Path('/tmp/a'),rel='a'),SimpleNamespace(path=Path('/tmp/b'),rel='b')]
        prepared=[];resolved=[]
        def prepare(project,version,**kwargs):
            self.assertTrue(kwargs['skip_lock']);prepared.append(project.rel)
            return dict(error=None,path=project.rel,prerelease=None,docs=[],locked=False,pin_changed=True)
        def lock(path,version,**kwargs):
            self.assertEqual(prepared,['a','b']);resolved.append(path.name)
            if fail:raise RuntimeError('fixture resolver failure')
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(migration.sys,'argv',['migrate','--version','3.20.0.dev9','--no-touch-assessed-on']))
            for name,value in [('resolve_target',('3.20.0.dev9',True)),('verify_on_index',None),('verify_engine_support',None),('read_pyproject_pin','3.20.0.dev6'),('read_lock_version','3.20.0.dev9'),('_rewrite_doc',False)]:stack.enter_context(patch.object(migration,name,return_value=value))
            stack.enter_context(patch.object(migration,'discover_projects',side_effect=[projects,[]]))
            stack.enter_context(patch.object(migration,'migrate_project',side_effect=prepare))
            stack.enter_context(patch.object(migration,'_run_uv_lock',side_effect=lock))
            stack.enter_context(patch.object(migration.subprocess,'check_output',return_value=b''))
            write=stack.enter_context(patch.object(migration,'write_version_file'))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code=migration.main()
            if fail:self.assertEqual(code,1);write.assert_not_called()
            else:self.assertEqual(code,0);write.assert_called_once_with('3.20.0.dev9')
        self.assertEqual(resolved,['a','b'])
    def test_every_manifest_precedes_any_lock(self):self.exercise()
    def test_lock_failure_never_advances_root_pin(self):self.exercise(fail=True)

class TrainingCredentialsTests(unittest.TestCase):
    def test_runtime_key_is_not_mistaken_for_a_local_training_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);project=rasa_projects.Project(path)
            manifest=path/'pyproject.toml'
            manifest.write_text('[tool.rasa-catalog]\nrequired-secrets = ["GEMINI_API_KEY"]\ntraining-secrets = []\n')
            self.assertEqual(rasa_projects.read_required_secrets(project), ['GEMINI_API_KEY'])
            self.assertEqual(rasa_projects.read_training_secrets(project), [])
            manifest.write_text('[tool.rasa-catalog]\nrequired-secrets = ["OPENAI_API_KEY"]\n')
            self.assertEqual(rasa_projects.read_training_secrets(project), ['OPENAI_API_KEY'])

if __name__=='__main__':unittest.main()
