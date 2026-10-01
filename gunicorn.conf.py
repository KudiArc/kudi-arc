bind = "0.0.0.0:5000"
workers = 2
timeout = 120
accesslog = "logs/access.log"
errorlog  = "logs/error.log"
preload_app = True

def post_fork(server, worker):
    import threading
    from app import fetch_fx_rates
    def loop():
        import time
        while True:
            fetch_fx_rates()
            time.sleep(300)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
