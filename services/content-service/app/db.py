from flask import current_app, g


def db():
    if "db" not in g:
        g.db = current_app.extensions["db"]()
    return g.db
