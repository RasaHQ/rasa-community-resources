"""Native model negative controls for the intentionally narrow inventory scope."""
import json
import socket
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inventory import inventory
from rasa.mantle.skills.skill import Skill, OrderedBlock
from rasa.mantle.skills.conditions import GatedTool

class ScopeControls(unittest.TestCase):
    def refuse(self, skill, message):
        with patch('rasa.mantle.skills.catalog.load_skill_catalog',return_value=SimpleNamespace(skills={'fixture':skill})), patch('rasa.mantle.tools.loader.load_tools_for_skill_catalog') as loader:
            with self.assertRaisesRegex(ValueError,message):
                inventory(Path(__file__).parent)
            loader.assert_not_called()

    def test_top_level_state_gate_refused_before_python_imports(self):
        self.refuse(Skill(id='fixture',tools=[GatedTool(name='read',requires='memory.ready')]),'explicit state')

    def test_block_state_gate_refused_before_python_imports(self):
        self.refuse(Skill(id='fixture',body=[OrderedBlock(block_id='check',tools=[GatedTool(name='read',requires='memory.ready')])]),'explicit state')

    def test_mcp_refused_before_python_imports(self):
        self.refuse(Skill(id='fixture',import_tool_names=frozenset({'mcp/server/read'})),'separate inventory adapter')

    def test_engine_managed_refused(self):
        self.refuse(Skill(id='fixture',engine_managed=True),'outside this fixture scope')

    def test_bundled_default_refused(self):
        self.refuse(Skill(id='fixture',is_default=True),'outside this fixture scope')

    def test_routing_conditions_refused(self):
        for changes in ({'precondition':'account_ready'},{'hidden':True},{'disabled':True}):
            with self.subTest(changes=changes):
                self.refuse(Skill(id='fixture',**changes),'explicit state')

if __name__ == '__main__':
    unittest.main()
