# Lessons Learned

## Schema changes require manual ALTER TABLE

**Pattern:** Adding a column to a SQLAlchemy model does NOT update the live database.
`Base.metadata.create_all()` is a no-op for existing tables — it never adds columns.

**Rule:** After adding any `Column(...)` to a model, immediately run:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('basecamp.db')
conn.execute('ALTER TABLE <table> ADD COLUMN <name> <TYPE>')
conn.commit()
"
```
Or note it in the PR so the user knows to run it. Always verify with `PRAGMA table_info(<table>)` before testing.