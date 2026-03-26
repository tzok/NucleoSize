import os
import json
import asyncio
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

DATA_FILE = "/data/na_lengths.json"
TEMP_FILE = "/data/na_lengths_temp.json"
METADATA_FILE = "/data/metadata.json"  # Stores ETag and Last-Modified
PDB_SEQRES_URL = "https://files.wwpdb.org/pub/pdb/derived_data/pdb_seqres.txt"

nav_lengths = {}
valid_pdb_ids = set()


class HealthCheckFilter(logging.Filter):
    """Filter out /health endpoint from access logs."""

    def filter(self, record):
        if hasattr(record, "args") and len(record.args) >= 3:
            request_line = record.args[2]
            if isinstance(request_line, str) and "/health" in request_line:
                return False
        return True


# Filter out healthcheck requests from uvicorn access logs
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


def get_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_metadata(headers):
    # Save the caching headers for future use (survives container restarts)
    metadata = {
        "etag": headers.get("etag"),
        "last-modified": headers.get("last-modified"),
    }
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f)


async def check_and_update():
    """Performs a conditional GET. Updates only if PDB has new data."""
    print("Checking PDB for updates...")
    metadata = get_metadata()
    headers = {}

    if metadata.get("etag"):
        headers["If-None-Match"] = metadata.get("etag")
    if metadata.get("last-modified"):
        headers["If-Modified-Since"] = metadata.get("last-modified")

    async with httpx.AsyncClient() as client:
        # We start a stream request. It will resolve the headers immediately.
        async with client.stream("GET", PDB_SEQRES_URL, headers=headers) as response:
            # 304 Not Modified means we already have the latest data!
            if response.status_code == 304:
                print("Data is up-to-date. No download needed.")
                return False

            response.raise_for_status()

            print("New data found! Downloading and parsing...")
            new_nav_lengths = {}
            new_valid_pdb_ids = set()
            async for line in response.aiter_lines():
                if line.startswith(">"):
                    parts = line.split()
                    pdb_id = parts[0][1:5].lower()
                    new_valid_pdb_ids.add(pdb_id)

                    if "mol:na" in line or "mol:nucleic" in line:
                        length_part = next(
                            (p for p in parts if p.startswith("length:")), None
                        )
                        if length_part:
                            length = int(length_part.split(":")[1])
                            new_nav_lengths[pdb_id] = (
                                new_nav_lengths.get(pdb_id, 0) + length
                            )

            # Prepare combined data for saving
            combined_data = {
                "nav_lengths": new_nav_lengths,
                "valid_pdb_ids": list(new_valid_pdb_ids),
            }

            # Save our atomic files
            with open(TEMP_FILE, "w") as f:
                json.dump(combined_data, f)
            os.replace(TEMP_FILE, DATA_FILE)

            # Save the new cache headers
            save_metadata(response.headers)

            # Swap RAM atomically
            global nav_lengths, valid_pdb_ids
            nav_lengths = new_nav_lengths
            valid_pdb_ids = new_valid_pdb_ids
            print(
                f"Update complete. Loaded {len(nav_lengths)} nucleic acid entries from {len(valid_pdb_ids)} total PDB IDs."
            )
            return True


async def periodic_updater():
    """Wakes up every 6 hours and checks if PDB has updated."""
    while True:
        try:
            await check_and_update()
        except Exception as e:
            print(f"Update failed: {e}. Will retry next cycle.")

        # Sleep for 6 hours.
        # Checking 4 times a day ensures we get Wednesday's update promptly
        # but prevents spamming the PDB FTP servers.
        await asyncio.sleep(60 * 60 * 6)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global nav_lengths, valid_pdb_ids

    if os.path.exists(DATA_FILE):
        print("Loading existing data from volume...")
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Handle both old format (direct dict) and new format (combined dict)
            if (
                isinstance(data, dict)
                and "nav_lengths" in data
                and "valid_pdb_ids" in data
            ):
                nav_lengths = data["nav_lengths"]
                valid_pdb_ids = set(data["valid_pdb_ids"])
            else:
                # Old format: assume it's just nav_lengths
                nav_lengths = data
                valid_pdb_ids = set(data.keys())

    # Always fire an immediate check on container startup/deployment
    # This also handles the first-time fetch if no DATA_FILE exists
    asyncio.create_task(check_and_update())

    updater_task = asyncio.create_task(periodic_updater())

    yield
    updater_task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/api/{pdbid}")
def get_length(pdbid: str):
    original_pdbid = pdbid.lower()
    # Handle new PDB ID format: pdb_0000xxxx -> xxxx
    if original_pdbid.startswith("pdb_0000"):
        pdbid = original_pdbid[8:]  # Extract last 4 characters
    else:
        pdbid = original_pdbid

    if pdbid in nav_lengths:
        return {"pdbid": original_pdbid, "total_na_length": nav_lengths[pdbid]}
    elif pdbid in valid_pdb_ids:
        return {"pdbid": original_pdbid, "total_na_length": 0}
    raise HTTPException(status_code=404, detail="PDB ID not found")


@app.get("/health")
def health_check():
    if not nav_lengths:
        raise HTTPException(status_code=503, detail="Data not loaded yet")
    return {
        "status": "healthy",
        "entries": len(nav_lengths),
        "total_pdb_ids": len(valid_pdb_ids),
    }
