import atexit
from app import create_app, start_scheduler, scheduler

# Tworzymy instancję aplikacji, aby przekazać ją do funkcji startującej
app = create_app()

def when_ready(server):
    """Uruchamia się, gdy serwer Gunicorn (master) jest gotowy."""
    print("Gunicorn master process jest gotowy. Uruchamiam scheduler...")
    start_scheduler(app)

def on_exit(server):
    """Uruchamia się, gdy Gunicorn się zamyka."""
    if scheduler.running:
        print("Gunicorn zamyka się. Zatrzymuję scheduler...")
        scheduler.shutdown()

# Ustawienia Gunicorna
bind = "0.0.0.0:5000"
workers = 3  # Możesz dostosować liczbę workerów
timeout = 120