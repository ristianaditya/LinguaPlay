import sys

def run():
    if len(sys.argv)==3 and sys.argv[1]=='--check-installation':
        from linguaplay.diagnostics import check_installation
        return check_installation(sys.argv[2])
    from linguaplay.ui import main
    return main()

if __name__ == '__main__':
    try:
        code=run()
    except Exception:
        import os
        from pathlib import Path
        import traceback
        logdir=Path(sys.argv[2]) if len(sys.argv)==3 and sys.argv[1]=='--check-installation' else Path(os.environ.get('LOCALAPPDATA','.'))/'LinguaPlay'
        logdir.mkdir(parents=True,exist_ok=True)
        logfile=logdir/'startup-error.log'; logfile.write_text(traceback.format_exc(),encoding='utf-8')
        if '--check-installation' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,f'Aplikasi belum dapat dibuka. Detail tersimpan di:\n{logfile}','LinguaPlay',0x10)
        code=1
    raise SystemExit(code)
