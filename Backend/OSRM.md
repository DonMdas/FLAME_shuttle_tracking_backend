# OSRM Usage Guide (Python)

This README provides a simple, beginner‑friendly explanation of how to use the **Open Source Routing Machine (OSRM)** to calculate **travel times**, **distances**, and **distance matrices** using nothing but Python.

You do **not** need Google Maps, API keys, Docker, accounts, or hosting services. OSRM provides a **free public server** you can call directly.

---

# 🚀 What Is OSRM?

OSRM (Open Source Routing Machine) is a super‑fast routing engine built on top of **OpenStreetMap (OSM)** data. It can compute:

* Driving routes
* Travel time (ETA)
* Distance between points
* Distance matrices

The best part:
✔ 100% Free
✔ No signup needed
✔ No API key
✔ Works globally (including India)
✔ Extremely fast

---

# 📌 OSRM Public Server

You can call the OSRM API directly:

```
http://router.project-osrm.org
```

This server supports:

* `/route` → turn‑by‑turn route + ETA
* `/table` → distance/time matrix

Coordinates must be in the format:

```
longitude,latitude
```

---

# 🛣️ 1. Get Travel Time (ETA) Between Two Points

Python example:

```python
import requests

# OSRM expects: LONGITUDE,LATITUDE
origin = "77.5946,12.9716"        # Example: Bangalore
destination = "77.6280,12.9344"   # Example destination

url = f"http://router.project-osrm.org/route/v1/driving/{origin};{destination}?overview=false"

res = requests.get(url).json()
duration_sec = res["routes"][0]["duration"]
distance_m = res["routes"][0]["distance"]

print("ETA (minutes):", duration_sec/60)
print("Distance (km):", distance_m/1000)
```

Output includes:

* `duration` → time in seconds
* `distance` → meters

---

# 📊 2. Generate a Distance Matrix (OSRM Table API)

This gives travel times between **many** points.

```python
import requests

coords = "77.5946,12.9716;77.6280,12.9344;77.6200,12.9100"  # Multiple lon,lat pairs

url = f"http://router.project-osrm.org/table/v1/driving/{coords}?annotations=duration"

res = requests.get(url).json()
matrix = res["durations"]

print(matrix)
```

Example output:

```
[
  [0, 350, 500],
  [360, 0, 420],
  [520, 430, 0]
]
```

Each cell `matrix[i][j]` is the travel time from point `i` → `j`.

---

# 🌏 3. When Should You Self‑Host OSRM?

The OSRM public server is great for:

* Prototyping
* Student projects
* Light to medium load

You should consider running your own OSRM server if:

* You need **heavy** usage (more than ~1000 requests/hour)
* You need **custom profiles** (bike, truck, EV)
* You want **offline** or private routing

For self‑hosting, OSRM provides Docker images:

```
docker run -t -i -p 5000:5000 osrm/osrm-backend
```

---

# ⚠️ Notes and Limitations

* Public OSRM sometimes rate‑limits heavy traffic
* Does **not** include live traffic (unlike Google Maps)
* Requires longitude,latitude order
* Free public server is shared by everyone

---

# 🧩 Summary

| Feature         | OSRM        | Google Maps   |
| --------------- | ----------- | ------------- |
| Free            | ✔ Yes       | ❌ No          |
| API Key         | ❌ No        | ✔ Required    |
| Traffic         | ❌ No        | ✔ Yes         |
| Distance Matrix | ✔ Unlimited | ❌ 25×25 limit |
| Python Ready    | ✔ Yes       | ✔ Yes         |

---

# 📝 Final Notes

Use OSRM whenever you want **free, fast, basic routing** without depending on commercial APIs. For academic projects, dashboards, route optimization, or logistics simulations, OSRM is perfect.

If you need help integrating OSRM with Flask, FastAPI, Leaflet, OpenLayers, or an ML pipeline, you can extend this README or ask for an advanced guide.
