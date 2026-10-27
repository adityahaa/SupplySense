"""Portable setup invoked by setup_windows.bat; no activation or policy changes."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import venv
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-launch',action='store_true',help='Install/check without starting the server (automation).')
    args=parser.parse_args()
    if sys.version_info[:2] not in [(3,11),(3,12)]:
        print('SupplySense setup requires Python 3.11 or 3.12.'); return 1
    target=ROOT/'.venv'
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    try:
        if not python.is_file():
            print('Creating local virtual environment...',flush=True)
            venv.EnvBuilder(with_pip=True).create(target)
        subprocess.run([str(python),'-c','import sys; assert sys.version_info[:2] in [(3,11),(3,12)], "Unsupported environment Python"'],check=True)
        print('Installing pinned application dependencies. Internet is required for this first setup.',flush=True)
        subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(ROOT/'requirements.txt')],check=True,cwd=ROOT)
        subprocess.run([str(python),str(ROOT/'scripts'/'launch.py'),'--check'],check=True,cwd=ROOT)
        print('Setup succeeded. Saved forecasting results are ready; no retraining is required.',flush=True)
        if not args.no_launch: return subprocess.call([str(python),str(ROOT/'scripts'/'launch.py')],cwd=ROOT)
        return 0
    except (OSError,subprocess.CalledProcessError) as exc:
        print(f'Setup failed: {exc}\nCheck internet access and the message above, then run setup_windows.bat again.');return 1
if __name__=='__main__': raise SystemExit(main())
