import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from converter import DataBridge

class MonitorHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".json") and "sugestao" in event.src_path:
            logging.info(f"Alteração detectada: {event.src_path}. Validando...")
            # Aqui você chamaria o seu validador/pytest
            # DataBridge.validar_e_salvar(...) 

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = "./" 
    event_handler = MonitorHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    print(f"Monitorando alterações em {path}...")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
