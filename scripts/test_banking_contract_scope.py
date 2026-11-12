"""Selection must distinguish absent examples from incomplete checked-in ones."""
from pathlib import Path
import tempfile
import unittest
from banking_contract_scope import selected


class BankingScopeTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def complete(self,name):
        for relative in ('examples/'+name+'/Makefile','examples/'+name+'/pyproject.toml',
                         'examples/'+name+'/uv.lock','.devcontainer/examples-'+name+'/devcontainer.json'):
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')

    def test_no_new_examples_is_explicit_empty_selection(self):
        self.assertEqual(selected(self.root),[])

    def test_present_complete_examples_are_selected_and_old_names_ignored(self):
        for name in ('jack-henry-symitar','jack-henry-silverlake','fiserv-premier','jack-henry-banking','fiserv-banking'):
            self.complete(name)
        self.assertEqual(selected(self.root),['jack-henry-symitar','jack-henry-silverlake','fiserv-premier'])

    def test_partial_example_fails_instead_of_silently_skipping(self):
        (self.root/'examples/jack-henry-symitar').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Incomplete example'):selected(self.root)


if __name__=='__main__':unittest.main()
