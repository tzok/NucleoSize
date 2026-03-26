import os
import json
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

DATA_FILE = "/data/na_lengths.json"
TEMP_FILE = "/data/na_lengths_temp.json"
METADATA_FILE = "/data/metadata.json"  # Stores ETag and Last-Modified
PDB_SEQRES_URL = "https://files.wwpdb.org/pub/pdb/derived_data/pdb_seqres.txt"

nav_lengths = {}


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
        headers["If-None-Match"] = metadata["etag"]
    if metadata.get("last-modified"):
        headers["If-Modified-Since"] = metadata["last-modified"]

    async with httpx.AsyncClient() as client:
        # We start a stream request. It will resolve the headers immediately.
        async with client.stream("GET", PDB_SEQRES_URL, headers=headers) as response:
            # 304 Not Modified means we already have the latest data!
            if response.status_code == 304:
                print("Data is up-to-date. No download needed.")
                return False

            response.raise_for_status()

            print("New data found! Downloading and parsing...")
            new_data = {}
            async for line in response.aiter_lines():
                if line.startswith(">"):
                    if "mol:na" in line or "mol:nucleic" in line:
                        parts = line.split()
                        pdb_id = parts[0][1:5].lower()
                        length_part = next(
                            (p for p in parts if p.startswith("length:")), None
                        )
                        if length_part:
                            length = int(length_part.split(":")[1])
                            new_data[pdb_id] = new_data.get(pdb_id, 0) + length

            # Save our atomic files
            with open(TEMP_FILE, "w") as f:
                json.dump(new_data, f)
            os.replace(TEMP_FILE, DATA_FILE)

            # Save the new cache headers
            save_metadata(response.headers)

            # Swap RAM atomically
            global nav_lengths
            nav_lengths = new_data
            print(f"Update complete. Loaded {len(nav_lengths)} nucleic acid entries.")
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
    global nav_lengths

    if os.path.exists(DATA_FILE):
        print("Loading existing data from volume...")
        with open(DATA_FILE, "r") as f:
            nav_lengths = json.load(f)

    # Always fire an immediate check on container startup/deployment
    # This also handles the first-time fetch if no DATA_FILE exists
    asyncio.create_task(check_and_update())

    updater_task = asyncio.create_task(periodic_updater())

    yield
    updater_task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/api/{pdbid}")
def get_length(pdbid: str):
    pdbid = pdbid.lower()
    if pdbid in nav_lengths:
        return {"pdbid": pdbid, "total_na_length": nav_lengths[pdbid]}
    raise HTTPException(
        status_code=404, detail="PDB ID not found or contains no nucleic acids"
    )
