# Data Annotation Platform

Django annotations hosted on Render; accounts, ratings and CSV snapshots stored in Supabase PostgreSQL.

## Local verification (2026-11-12)

The production Docker image builds successfully. All 12 PostgreSQL regression
tests pass and migrations match the models. The non-root Gunicorn container was
tested with Render-style hostname, port, and forwarded HTTPS settings: login and
admin CSS both returned HTTP 200, and Django's deployment checks passed.
This is local verification, not a live Supabase connection or Render deployment.
Complete the setup and real-domain checks below before collecting study data.

Render runs Django and serves the images. Supabase stores accounts, sessions,
ratings, and CSV snapshots. No Supabase Auth/API keys or Storage buckets are needed.
The image dataset is bundled in the Docker image and survives redeploys.

## 1. Publish a clean source repository

IMPORTANT: this checkout's old Git history contains a SQLite database.
Do not push its existing history. Create a fresh private GitHub repository from
the current source files, without copying .git or db.sqlite3.

Include:

- annotator/, config/, templates/, Images/, deploy/, .github/
- manage.py, gunicorn.conf.py, pyproject.toml, uv.lock
- Dockerfile, .dockerignore, render.yaml, .gitignore, .python-version
- README.md, .env.example, compose.yaml

Exclude .env and any real credentials, .venv/, staticfiles/, backups/,
all SQLite databases and .DS_Store files. Initialize Git in that separate clean
folder and publish it as a new private repository. Do not delete this working copy.
Make sure Images/ and both new migration files are committed, not merely present
locally. The GitHub workflow tests the PostgreSQL workflow on pushes.

### Clean GitHub upload commands

Create a new empty folder (the command stops if it already exists). This copies
only source and dataset files, not the old Git history or local database:

```sh
cd "/Users/jzheng/Desktop/Data Annotation Platform"
mkdir "../Data-Annotation-Platform-upload" &&
tar --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' -cf - annotator config templates Images deploy .github manage.py gunicorn.conf.py pyproject.toml uv.lock Dockerfile .dockerignore render.yaml .gitignore .python-version README.md .env.example compose.yaml |
tar -xf - -C "../Data-Annotation-Platform-upload"
```

If the directory already exists, stop and choose a different empty destination.
On GitHub create a NEW private repository named Data-Annotation-Platform-cloud,
without a README, license, or gitignore. Replace YOUR-USERNAME below:

```sh
cd "../Data-Annotation-Platform-upload"
git init -b main
git add .
git status --short
git diff --cached --stat
```

Review the staged files for credentials and private data before proceeding:

```sh
git commit -m "Initial Render and Supabase deployment"
git remote add origin https://github.com/YOUR-USERNAME/Data-Annotation-Platform-cloud.git
git push -u origin main
```

Use this new checkout for future development. Your original checkout is preserved.
If old history was already pushed, this does not erase those copies: restrict access
and rotate any exposed credentials.

## 2. Create the Supabase database

1. Create a Supabase project and retain its database password privately.
2. In SQL Editor, execute [supabase.sql](deploy/supabase.sql). This creates the private
   django schema. Keep django OUT of the Data API exposed schemas list.
3. Open **Connect → Session pooler → View parameters**.
4. Copy the exact host and user. The user normally looks like
   postgres.YOUR_PROJECT_REFERENCE. Use database postgres and port 5432.
   Do not copy the transaction pooler on port 6543.

Use the DATABASE PASSWORD here, not a Supabase anon key or service_role API key.
This setup assumes a new database/schema, not importing the old local test users.

## 3. Create the Render service

1. On Render, select **New → Blueprint**, connect the clean GitHub repository,
   and select its main branch. Render reads the root render.yaml.
2. Review the service's region and paid Starter plan before confirming.
   Prefer a region close to the Supabase project.
3. Supply the four prompted secret/configuration values:

| Variable | Value |
| --- | --- |
| DJANGO_SECRET_KEY | Random secret of at least 50 characters |
| POSTGRES_HOST | Exact Supabase session-pooler hostname, without a URL scheme |
| POSTGRES_USER | Exact Supabase session-pooler username |
| POSTGRES_PASSWORD | Your Supabase database password |

Generate the Django secret locally with:

```sh
openssl rand -hex 32
```

Store the output in Render, not in source control.
The Blueprint supplies the remaining settings: postgres database, port 5432,
required SSL, private schema, production settings, debug disabled, and trusted
HTTPS proxy. The Render hostname is automatically allowed by Django.

4. Deploy. The build installs locked dependencies and collects static files;
   pre-deploy runs migrations; Gunicorn then starts the website.
   Render does not run the local Compose file.

The Blueprint uses a paid service because pre-deploy commands and Shell are part
of this workflow. No Render PostgreSQL instance is needed; Supabase is the database.

## 4. Create your researcher login

After successful deployment, open the Render service's **Shell** and run:

```sh
/app/.venv/bin/python manage.py createsuperuser --settings=config.settings
```

Choose a new username and strong password. Visit https://YOUR-SERVICE.onrender.com/admin/,
log in, and add a strong access code under Access codes. Do not use tempadmin123
or access code 123; those local development credentials are not migrated.

Share the root URL with annotators. They select **Create an account**, then supply
their email, a password (with confirmation), and an active access code. Returning
participants log in with email and password. Emails are case-insensitive; the
shared access code is required only for registration. Disabling a code stops new
registrations; disable a user in Django Admin to revoke that user's access.

Run `manage.py migrate` before deploying this authentication change. Existing
username-only accounts and their ratings remain intact, but can no longer log in
with a shared code. Do not automatically assign these accounts to someone based
on a claimed username. After independently verifying ownership, an administrator
can set the existing user's email and password and create an `EmailAccount` record
linked to that user with the lowercase email through the Django shell. This keeps
the existing user ID and ratings. New registrations receive an opaque internal
username, which remains the identifier in CSV exports. Researcher admin login is
unchanged. Email ownership verification at registration is not included.

### Password recovery and CSV deletion

The login page's **Forgot password?** link sends a single-use recovery link valid
for one hour. Only active registered email accounts with usable passwords receive
it; the confirmation page is the same for unknown emails. Local DEBUG mode prints
the email and reset link in the server terminal. Production requires `EMAIL_HOST`,
`EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL`.
Use `EMAIL_USE_TLS=1` for STARTTLS (normally port 587), or `EMAIL_USE_TLS=0` and
`EMAIL_USE_SSL=1` for implicit TLS (normally port 465). Apply ingress rate limits
to password-reset requests as well as login and registration. Administrators can
also set a user's password from Django Admin's Users page after verifying ownership.

In Django Admin, **Annotator result CSVs** supports individual deletion and the
**Delete selected** bulk action for superusers or staff with the CSV delete
permission. Deletion removes only the stored CSV snapshot, preserving the user
and ratings. A later rating save or edit regenerates the CSV. To remove underlying
responses, delete the relevant **Evaluation ratings** as well.

## 5. Verify before collecting real responses

- Sign in as a test annotator and verify the study images load.
- Save a few scores, log out, return with the same email and password, and verify they remain.
- Log in as the researcher and download both that CSV and the all-CSVs ZIP.
- Redeploy and verify those saved ratings remain in Supabase.
- Configure database backups in Supabase and test a restore into a separate project.
- Configure ingress login rate limiting before opening the service broadly.
  Apply the same rate limiting to registration.

Do not run manage.py test against the production Supabase database. CI uses an
isolated PostgreSQL service.

## Custom domain and troubleshooting

For a custom domain, add it in Render and set DJANGO_ALLOWED_HOSTS to that hostname
(no https://). Multiple domains are comma-separated. The Render hostname stays allowed.

- Database connection failure: recheck session-pooler host/user/password and port 5432.
- "No schema selected": run supabase.sql first. We intentionally do not fall back
  to public, which could expose Django auth/session tables via the Data API.
- Redirect loop: ensure DJANGO_TRUST_PROXY=1 on Render.
- Missing images: verify Images/ is included in the GitHub repository.
- Missing admin CSS: inspect the collectstatic build step.

References: [Render Django](https://render.com/docs/deploy-django),
[Render Blueprints](https://render.com/docs/blueprint-spec),
[Supabase connections](https://supabase.com/docs/guides/database/connecting-to-postgres).

## Local development

Install uv and Docker, then run:

```sh
docker compose up -d --wait postgres
uv sync --frozen
uv run manage.py migrate
uv run manage.py createsuperuser
uv run manage.py runserver
```

Visit http://127.0.0.1:8000/admin/ to create an access code. Local defaults are in
[.env.example](.env.example). Django does not automatically read .env files;
export environment overrides in your shell. Never deploy development credentials.

## Data and maintenance

PostgreSQL is the source of truth; CSV is the export format. Click Save or
Save-and-next before leaving an example: there is no autosave.
Ratings and CSV snapshots commit together. In Django Admin, open Annotator result
CSVs for individual downloads or Download all CSVs as ZIP (all users, regardless
of the current filter).

Historical migrations and legacy models are retained for migration compatibility.
Keep [Images/](Images/), [annotator/data/](annotator/data/) and every migration.
Local databases, environments, generated static files and backups are ignored by Git.
