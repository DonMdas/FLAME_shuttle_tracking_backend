# getDeviceInfo API Endpoint Documentation

## Overview

The `getDeviceInfo` API endpoint is part of the EERA GPS House tracking platform. It is used to retrieve **real‑time information** about a specific GPS tracking device such as location, status, motion, ignition, battery level, and distance metrics.

This endpoint is typically consumed by fleet management dashboards, mobile apps, or backend services that require up‑to‑date tracking data.

---

## Base URL

```
https://track.eeragpshouse.com
```

---

## Endpoint Path

```
/api/middleMan/getDeviceInfo
```

The `middleMan` module appears to act as a proxy layer between devices and the tracking backend.

---

## HTTP Method

**GET**

---

## Query Parameters

### `accessToken` (required)

A Base64‑encoded token that contains:

* Authentication information
* Device identifier (IMEI or internal ID)
* Possibly user/session metadata
* Token expiration or signing data

The token determines **which device** the endpoint returns data for.

Since no additional parameters like IMEI or deviceId are passed separately, the device identity is included **inside the token itself**.

### Example

```
https://track.eeragpshouse.com/api/middleMan/getDeviceInfo?accessToken=BASE64TOKEN...
```

---

## Behavior of the Endpoint

* The endpoint returns **information for exactly one device**.
* Different devices require **different tokens**, since each token internally encodes a unique device ID.
* The token must be valid; otherwise the API will return an error or empty result.

---

## Example Response

Below is a real sample response structure returned from the API:

```json
{
  "successful": true,
  "message": "",
  "object": [
    {
      "attributes": {
        "power": null,
        "ignition": false,
        "charge": true,
        "batteryLevel": 4000,
        "ac": null,
        "door": null,
        "panic": null,
        "alarm": null,
        "motion": false,
        "totalDistance": 2428239.65,
        "todayDistance": 138811.63
      },
      "name": "KUMAR",
      "companyName": "eerademo",
      "deviceUniqueId": "356218600094070",
      "timestamp": "2025-11-22T11:31:54.062+00:00",
      "serverTime": "2025-11-22T11:31:35.187+00:00",
      "deviceTime": "2025-11-22T11:31:35.187+00:00",
      "fixTime": "2025-11-22T11:16:39.000+00:00",
      "lastStatusUpdate": "2025-11-22T11:31:35.187+00:00",
      "valid": true,
      "latitude": 18.4439288888889,
      "longitude": 73.9106077777778,
      "altitude": 0,
      "speed": 0,
      "course": 213,
      "address": null,
      "accuracy": 0
    }
  ]
}
```

---

## Response Field Description

| Field                  | Meaning                                      |
| ---------------------- | -------------------------------------------- |
| `successful`           | Indicates whether the API call succeeded     |
| `deviceUniqueId`       | IMEI of the device                           |
| `attributes`           | Device‑specific operational and sensor data  |
| `ignition`             | Whether the vehicle engine is ON/OFF         |
| `charge`               | Charging status                              |
| `batteryLevel`         | Remaining battery (typically in mV)          |
| `motion`               | Whether the device is currently moving       |
| `totalDistance`        | Lifetime distance travelled                  |
| `todayDistance`        | Distance travelled today                     |
| `latitude`/`longitude` | Current location                             |
| `speed`                | Current speed in km/h                        |
| `course`               | Direction of travel (0–360°)                 |
| `fixTime`              | GPS timestamp of the last valid location fix |

---

## Key Points About the Token

* Each **device has its own unique access token**.
* The token itself internally encodes the IMEI or device ID.
* The endpoint cannot retrieve multiple devices at once; one token = one device.
* Tokens may be user‑specific or time‑limited depending on system design.

---

## Common Use Cases

* Fetching live tracking data
* Displaying device status on a map
* Building real‑time fleet dashboards
* Monitoring ignition, movement, or battery levels
* Integrating with third‑party logistics systems

---

## Notes

* Only GET method is supported.
* The server returns JSON.
* The API does not require API keys or headers apart from the `accessToken`.

