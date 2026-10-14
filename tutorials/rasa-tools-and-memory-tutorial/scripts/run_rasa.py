"""Run Rasa with this tutorial's explicitly selected local credential file."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values

PROJECT = Path(__file__).resolve().parents[1]


def environment(path, inherited):
    if not path.is_file():
        raise ValueError('Create the selected .env file and add your local credentials')
    values = dotenv_values(path, interpolate=False)
    license_value = values.get('RASA_LICENSE') or values.get('RASA_PRO_LICENSE')
    if not license_value:
        raise ValueError('The selected file needs RASA_LICENSE; inherited licences are not used')
    # Do not accidentally pick another project's credentials from the shell.
    env = {key: value for key, value in inherited.items()
           if not any(word in key.upper() for word in ('KEY', 'TOKEN', 'SECRET', 'LICENSE', 'PASSWORD', 'CREDENTIAL'))}
    env.update({key: value for key, value in values.items() if value is not None})
    env.pop('RASA_PRO_LICENSE', None)
    env['RASA_LICENSE'] = license_value
    # The selected file was read above; block SDK loading a second .env.
    env['PYTHON_DOTENV_DISABLED'] = 'true'
    env['OPENAI_API_KEY'] = values.get('OPENAI_API_KEY') or ''
    return env


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=PROJECT / '.env')
    parser.add_argument('rasa_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.rasa_args:
        parser.error('Supply a Rasa command, such as train or inspect')
    try:
        env = environment(args.env_file, os.environ)
    except ValueError as error:
        parser.error(str(error))
    raise SystemExit(subprocess.run([sys.executable, '-m', 'rasa', *args.rasa_args], cwd=PROJECT, env=env).returncode)
