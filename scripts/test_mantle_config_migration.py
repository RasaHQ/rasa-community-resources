"""Regress the 3.22 selector move without altering tool or channel settings."""
from pathlib import Path
import tempfile
import unittest
from migrate_mantle_config import migrate


class ConfigMigrationTests(unittest.TestCase):
    def prepare(self, directory):
        root = Path(directory)
        (root / 'agent.yml').write_text('agent:\n  persona: Help with fictional cases.\n')
        (root / 'integrations.yml').write_text(
            'llm:\n  model_group: "local_model"\n\n'
            'model_groups:\n  - id: local_model\n    models: []\n'
            'channels:\n  rest:\n    enabled: true\n')
        return root

    def test_selector_moves_and_channels_and_model_groups_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            before = (root / 'integrations.yml').read_text()
            migrate(root)
            self.assertIn('orchestrator:\n  model_group: local_model\n', (root / 'agent.yml').read_text())
            self.assertEqual((root / 'integrations.yml').read_text(), before.split('\n\n', 1)[1])
            self.assertEqual(migrate(root), [])

    def test_conflicting_template_changes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            (root / 'integrations.provider.yml.in').write_text('llm:\n  model_group: another_model\n')
            before = {p: p.read_bytes() for p in root.iterdir()}
            with self.assertRaisesRegex(ValueError, 'alternate model group'):
                migrate(root)
            self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir()})

    def test_existing_conflict_and_extra_legacy_fields_are_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            agent = root / 'agent.yml'
            agent.write_text(agent.read_text() + 'orchestrator:\n  model_group: different\n')
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                migrate(root)
            (root / 'integrations.yml').write_text('llm:\n  model_group: local_model\n  temperature: 0.1\n')
            with self.assertRaisesRegex(ValueError, 'other settings'):
                migrate(root)

    def test_dry_run_checks_templates_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            template = root / 'integrations.scripted.yml.in'
            template.write_text((root / 'integrations.yml').read_text())
            before = {p: p.read_bytes() for p in root.iterdir()}
            changed = migrate(root, dry_run=True)
            self.assertEqual(len(changed), 3)
            self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir()})

    def test_existing_authentication_precondition_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            path = root / 'agent.yml'
            guard = '  preconditions:\n    authenticated:\n      satisfied_when: session.project.authenticated\n      resolve_with: authenticate\n'
            path.write_text(path.read_text() + 'orchestrator:\n' + guard)
            migrate(root)
            self.assertIn('orchestrator:\n  model_group: local_model\n' + guard, path.read_text())


if __name__ == '__main__':
    unittest.main()
