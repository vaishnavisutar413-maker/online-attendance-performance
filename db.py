import psycopg2
import psycopg2.extras
from flask import current_app, g


def get_db():
    if "db" not in g:
        c = current_app.config
        g.db = psycopg2.connect(
            host=c["DB_HOST"], port=c["DB_PORT"], dbname=c["DB_NAME"],
            user=c["DB_USER"], password=c["DB_PASSWORD"],
        )
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=None, one=False):
    cur = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params or ())
    rows = cur.fetchall() if cur.description else []
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=None, returning=False):
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(sql, params or ())
        result = cur.fetchone() if returning else None
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def init_app(app):
    app.teardown_appcontext(close_db)
