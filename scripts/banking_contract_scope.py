#!/usr/bin/env python3
"""Select complete direct banking examples; an empty checkout is explicit."""
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROJECTS=('jack-henry-symitar','jack-henry-silverlake','fiserv-premier-11.0.0-prm')


def selected(root=ROOT):
    projects=[]
    for name in PROJECTS:
        project=root/'examples'/name
        if not project.exists():continue
        required=(project/'Makefile',project/'pyproject.toml',project/'uv.lock',
                  root/'.devcontainer'/('examples-'+name)/'devcontainer.json')
        for path in required:
            if not path.is_file():raise ValueError('Incomplete example: '+str(path.relative_to(root)))
        projects.append(name)
    return projects


if __name__=='__main__':
    projects=selected()
    print('Selected: '+', '.join(projects) if projects else 'No direct banking contract examples are present; nothing to test on this revision.')
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:
        output.write('projects='+json.dumps(projects)+'\n')
