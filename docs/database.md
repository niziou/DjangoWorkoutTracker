# Database setup

The app stores workouts in a local SQLite database by default:

```bash
data/workouts.sqlite3
```

That file is intentionally ignored by git. Keep backups of it if the app is still running locally:

```bash
cp data/workouts.sqlite3 data/workouts.backup.sqlite3
```

You can change the local SQLite file location without changing code:

```bash
DJANGO_SQLITE_PATH=/absolute/path/workouts.sqlite3 python manage.py runserver
```

For a server or cloud deployment, set `DATABASE_URL` to a managed database URL. PostgreSQL is the recommended target for AWS/RDS or most platform deployments:

```bash
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME python manage.py migrate
```

After importing data into production, run migrations against that database:

```bash
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME python manage.py migrate
```

To move local data from SQLite to PostgreSQL later:

```bash
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.Permission > data/export.json
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME python manage.py migrate
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME python manage.py loaddata data/export.json
```
