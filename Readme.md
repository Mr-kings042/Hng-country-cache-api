# Countries Cache API

A small FastAPI application that fetches country data from the RestCountries API, matches currency codes to exchange rates, computes an estimated GDP, caches the results in a database (SQLite by default, MySQL optional), and exposes CRUD and utility endpoints.

This README covers: setup, running locally, Docker, environment variables, dependencies, and API documentation.

## Requirements

- Python 3.10+
- (For local dev) `venv` or other virtual environment
- Docker & Docker Compose (for containerized MySQL and running the app in a container)
## Setting up
```bash
git clone https://github.com/Mr-kings042/Hng-country-cache-api.git
cd Hng-country-cache-api
```
## Dependencies

The project uses these main Python packages:

- fastapi
- uvicorn[standard]
- sqlalchemy
- aiosqlite
- aiomysql (when using MySQL)
- httpx
- python-dotenv
- pillow

Install them with pip (recommended: inside a virtualenv):

```powershell
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

If you don't have a `requirements.txt`, install directly:

```powershell
pip install fastapi "uvicorn[standard]" sqlalchemy aiosqlite aiomysql httpx python-dotenv pillow
```

## Environment

Create a `.env` file in the project root or set environment variables in your environment. Important variables:

- `DATABASE_URL` — optional full async DB URL (e.g. `mysql+aiomysql://user:pass@host:3306/dbname` or `sqlite+aiosqlite:///./countries.db`). If set, it takes precedence.
- `MYSQL_HOST`, `DATABASE_HOST` — host for MySQL (compose service name is `db` when using docker-compose)
- `MYSQL_PORT`, `DATABASE_PORT` — port for MySQL (default 3306)
- `MYSQL_USER` — MySQL username (used when building DSN)
- `MYSQL_PASSWORD` — MySQL password
- `MYSQL_DATABASE` — MySQL database name
- `COUNTRY_API_URL` — REST Countries endpoint (default used by app: `https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies`)
- `RATE_API_URL` — Exchange rates endpoint (default used by app: `https://open.er-api.com/v6/latest/USD`)

Example `.env` for Docker Compose (development):

```
MYSQL_ROOT_PASSWORD=rootpass
MYSQL_DATABASE=countries
MYSQL_USER=user
MYSQL_PASSWORD=password
DATABASE_HOST=db
DATABASE_PORT=3306
COUNTRY_API_URL=https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies
RATE_API_URL=https://open.er-api.com/v6/latest/USD
```

## Running locally (SQLite - quick)

This is the fastest way to run the app locally without Docker or MySQL:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# Use the default local SQLite DB URL
set DATABASE_URL=sqlite+aiosqlite:///./countries.db
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive OpenAPI UI.

## Running with Docker Compose (MySQL)

The repository includes a `docker-compose.yaml` that launches a MySQL service and the web app. The web service is configured to construct a MySQL DSN from environment variables and will use `aiomysql` to connect.

Start services:

```powershell
docker-compose up --build
```

This starts MySQL and the web app. The compose configuration is development-oriented (it mounts the project into the container). For production, remove source mounts and provide secure secrets for DB credentials.

## Switching between MySQL and SQLite

- To use MySQL (recommended for production), either set `DATABASE_URL` to an async MySQL URL (preferred) or provide `MYSQL_*` env vars and a `DATABASE_HOST`.
- To use SQLite for local development, set `DATABASE_URL=sqlite+aiosqlite:///./countries.db`.

## API Endpoints

All endpoints return JSON.

Base URL: `/`

1. POST /countries/refresh

- Description: Fetches all countries and exchange rates, computes estimated GDP, and caches/updates records in the database. Also generates `cache/summary.png`.
- Success: 200 (or 201) with body:

```json
{ "message": "Refresh completed", "last_refreshed_at": "2025-10-26T18:00:00Z" }
```
- Errors:
	- 503 Service Unavailable: { "error": "External data source unavailable", "details": "Could not fetch data from [API name]" }

2. GET /countries

- Description: Returns all cached countries.
- Query params (optional):
	- `region` (e.g. `?region=Africa`)
	- `currency` (e.g. `?currency=NGN`)
	- `sort=gdp_desc` (orders by estimated_gdp descending)
- Example response (array of country objects):

```json
[
	{
		"id": 1,
		"name": "Nigeria",
		"capital": "Abuja",
		"region": "Africa",
		"population": 206139589,
		"currency_code": "NGN",
		"exchange_rate": 1600.23,
		"estimated_gdp": 25767448125.2,
		"flag_url": "https://flagcdn.com/ng.svg",
		"last_refreshed_at": "2025-10-22T18:00:00Z"
	}
]
```

3. GET /countries/{name}

- Description: Get a single country by name (case-insensitive).
- Success: 200 with country object.
- 404: { "error": "Country not found" }

4. DELETE /countries/{name}

- Description: Delete the country record by name (case-insensitive).
- Success: 200: { "message": "Country deleted" }
- 404: { "error": "Country not found" }

5. GET /status

- Description: Returns cache status: total countries and last refresh timestamp.
- Example response:

```json
{
	"total_countries": 250,
	"last_refreshed_at": "2025-10-22T18:00:00Z"
}
```

6. GET /countries/image

- Description: Serve the generated summary image `cache/summary.png`.
- Success: 200 with image/png content.
- 404: `{ "error": "Summary image not found" }`

## Validation and Error Formats

- 400 Bad Request: { "error": "Validation failed", "details": { "field": "is required" } }
- 404 Not Found: { "error": "Country not found" }
- 500 Internal Server Error: { "error": "Internal server error" }
- 503 External API failure: { "error": "External data source unavailable", "details": "Could not fetch data from [API name]" }

## Notes & Tips

- The refresh process:
	- Uses the first currency in the country's `currencies` array.
	- If a country has no currencies, it stores `currency_code=null`, `exchange_rate=null`, `estimated_gdp=0`.
	- If a currency is present but not found in exchange rates, `exchange_rate=null` and `estimated_gdp=null`.
	- Random multiplier between 1000-2000 is generated per country on each refresh.

- Image generation: After a successful refresh an image is saved to `cache/summary.png` containing total countries, top 5 by estimated_gdp, and last refreshed timestamp.

- If you run the app locally but want to use the Dockerized MySQL, start compose first (`docker-compose up`) then run the web image or set `DATABASE_URL` to point at the running MySQL.

## Troubleshooting

- `Can't connect to MySQL server on 'db'`: means your process cannot resolve the hostname `db`. Use docker-compose (the service name `db` is only resolvable inside the compose network) or set `DATABASE_URL` to a reachable address when running locally.
- If `/countries/refresh` fails with 503, check logs for which external API failed and re-run. External APIs may be rate-limited or temporarily unavailable.


