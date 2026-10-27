"""Check the local app environment and start the server on loopback only."""
from pathlib import Path
import argparse
import importlib.util
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--port',type=int,default=8501)
    args=parser.parse_args()
    if not 1<=args.port<=65535:
        print('Choose a port between 1 and 65535.');return 1
    missing=[p for p in ['streamlit','pandas','numpy','plotly'] if importlib.util.find_spec(p) is None]
    if missing:
        print('Missing application libraries: '+', '.join(missing)+'. Run setup_windows.bat.');return 1
    sys.path.insert(0,str(ROOT))
    try:
        from supplysense.artifacts import load_bundle
        available=[p for p in [ROOT/'results/improved_results.zip',ROOT/'results/trained_results.zip',ROOT/'results/public_results.zip'] if p.is_file()]
        if not available: raise ValueError('Saved result ZIP files are missing. Extract the complete SupplySense project ZIP including results/.')
        b=load_bundle(available[0].read_bytes())
        print(f"Validated {available[0].name}: {b['test_predictions'].model.nunique()} models; {b['test_predictions'].id.nunique()} series.",flush=True)
    except Exception as exc:
        print(f'Cannot load saved results: {exc}');return 1
    if args.check: return 0
    with socket.socket() as probe:
        try: probe.bind(('127.0.0.1',args.port))
        except OSError:
            print(f'Port {args.port} is already in use. Open http://localhost:{args.port} or stop the existing server.');return 1
    print(f'Open http://localhost:{args.port}\nKeep this terminal open. Press Ctrl+C to stop.',flush=True)
    try:
        return subprocess.call([sys.executable,'-m','streamlit','run',str(ROOT/'app.py'),
            '--server.address','127.0.0.1','--server.port',str(args.port),'--browser.gatherUsageStats','false'],cwd=ROOT)
    except KeyboardInterrupt:
        print('\nSupplySense stopped.');return 0
if __name__=='__main__': raise SystemExit(main())
