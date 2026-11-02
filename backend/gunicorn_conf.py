"""Gunicorn configuration for the school-timetable API.

Process supervision (user, restart policy, environment variables) is owned by
systemd — see ``deploy/school-timetable.service``. This file only describes
gunicorn itself.

Logs are written to stdout/stderr so systemd/journald owns rotation and
retention::

    journalctl -u school-timetable -f

Application-level logs (``app.log`` / ``error.log``) are handled by Django's
``LOGGING`` config in ``config/settings.py``.
"""

# Loopback only: nginx proxies /school-timetable/api/ to this address.
# Never bind 0.0.0.0 here — that would expose gunicorn directly to the internet
# and bypass the nginx path prefix.
bind = "127.0.0.1:8014"

# SQLite is the only datastore; keep the worker count modest to reduce write
# contention while still allowing concurrent reads.
workers = 2
threads = 2
worker_class = "sync"

timeout = 60
graceful_timeout = 30
keepalive = 5

# systemd captures stdout/stderr; journald rotates and vacuums them.
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Behind nginx: keep the real client IP in the access log.
access_log_format = (
    '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(D)sus'
)
