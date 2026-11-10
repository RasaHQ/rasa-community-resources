"""Prepare the newest eligible Rasa candidate; daily CI tests before proposing it."""
from pathlib import Path
import argparse
import json
import subprocess
from packaging.version import Version
from index import discover

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path)
args=parser.parse_args()
report=discover()
if args.report:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
target=report['selected']['version'];current=(root/'RASA_PRO_VERSION').read_text().strip()
if not report['selected']['mantlePresent']: raise SystemExit(f'{target} lacks rasa.mantle; migration required, no fallback')
if Version(target)<Version(current): raise SystemExit('Index would downgrade the catalog; investigation required')
if target!=current:
    subprocess.run(['python3','scripts/migrate_rasa_pro.py','--version',target,'--no-touch-assessed-on'],cwd=root,check=True)
    (root/'RASA_RELEASE.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'changed':target!=current,'version':target}))
