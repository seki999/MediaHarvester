if __name__ == '__main__':
    import sys
    try:
        if '--worker' in sys.argv:
            from mediaharvester.worker import worker_main
            worker_main()
        else:
            from mediaharvester.app import main
            main()
    except Exception:
        import traceback
        from pathlib import Path
        if '--smoke-output' in sys.argv:
            output=Path(sys.argv[sys.argv.index('--smoke-output')+1]); output.mkdir(parents=True,exist_ok=True)
            (output/'fatal.txt').write_text(traceback.format_exc(),'utf-8')
        else:
            from mediaharvester.config import DATA
            (DATA/'startup-error.log').write_text(traceback.format_exc(),'utf-8')
            from PySide6.QtWidgets import QApplication,QMessageBox
            app=QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None,'MediaHarvester','程序启动失败，详情见 '+str(DATA/'startup-error.log'))
        sys.exit(1)
