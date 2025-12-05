import asyncio
import httpx

# 1. Configuration (Must match your .env or defaults)
OSRM_URL = "http://router.project-osrm.org"
# If running local docker, use: "http://localhost:5000"

async def test_osrm():
    # 2. Coordinates from your specific log (Symbiosis Campus area)
    # Format is (lat, lon)
    origin = (18.525352, 73.73255)
    dest = (18.518468, 73.765785) # Bavdhan Guard Post

    # OSRM expects: lon,lat
    coords_string = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    
    # 3. Construct the URL (Exact same parameters as your service)
    url = f"{OSRM_URL}/route/v1/driving/{coords_string}?overview=false&steps=false&annotations=true"

    print(f"Testing URL: {url}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Success!")
                print(f"Duration: {data['routes'][0]['duration']} seconds")
            else:
                print("❌ Server Error")
                print(response.text)
                
        except Exception as e:
            print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_osrm())