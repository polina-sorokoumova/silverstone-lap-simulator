
import math
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# ============================================================
# 1. CAR MODEL PARAMETERS
# ============================================================
# Simplified model, NOT real F1 telemetry.
# SI units: metres, seconds, kilograms.

MU = 2.1                  # Assumed tire-road grip coefficient
G = 9.81                  # Gravitational acceleration, m/s^2

V_TOP = 350.0 / 3.6       # Speed limit, m/s

A0 = 14.0                 # Acceleration at low speed, m/s^2
K = A0 / V_TOP**2         # Acceleration decreases with speed

DECEL_BASE = 26.0         # Assumed base braking deceleration, m/s^2
DECEL_AERO = 0.0022       # Additional braking: coefficient, 1/m

C_DOWNFORCE = 0.006       # Downforce per unit mass: coefficient, 1/m

TARGET_DS = 1.0           # Target spatial resolution, metres

COORD_SMOOTH_WINDOW = 9   # Odd number of samples
CURVATURE_SMOOTH_WINDOW = 15

MAX_ITER = 1000
TOLERANCE = 1e-7


# ============================================================
# 2. PHYSICAL MODEL
# ============================================================

def corner_speed(curvature):
    """Maximum speed allowed by the lateral grip model."""
    curvature = abs(float(curvature))

    if curvature < 1e-12:
        return V_TOP

    # v^2 * curvature <= MU * (G + C_DOWNFORCE * v^2)
    denominator = curvature - MU * C_DOWNFORCE

    if denominator <= 0:
        return V_TOP

    return min(
        math.sqrt(MU * G / denominator),
        V_TOP
    )


def braking(v):
    """Positive magnitude of braking deceleration, m/s^2."""
    return DECEL_BASE + DECEL_AERO * v**2


def acceleration(v):
    """Available forward acceleration, m/s^2."""
    return max(A0 - K * v**2, 0.0)


# ============================================================
# 3. PERIODIC SMOOTHING AND DIFFERENTIATION
# ============================================================

def smooth_circular(values, window):
    """Moving average with periodic boundary conditions."""
    values = np.asarray(values, dtype=float)

    if window <= 1:
        return values.copy()

    if window % 2 == 0:
        window += 1

    if window > len(values):
        raise ValueError("Smoothing window exceeds data length.")

    pad = window // 2
    kernel = np.ones(window, dtype=float) / window

    extended = np.concatenate((
        values[-pad:],
        values,
        values[:pad]
    ))

    return np.convolve(extended, kernel, mode="valid")


def periodic_derivative(values, ds):
    """Central difference on a closed loop."""
    return (
        np.roll(values, -1) - np.roll(values, 1)
    ) / (2.0 * ds)


def calculate_curvature(x, y, ds):
    """Signed curvature of a periodic planar trajectory, 1/m."""
    dx = periodic_derivative(x, ds)
    dy = periodic_derivative(y, ds)

    ddx = (
        np.roll(x, -1) - 2.0 * x + np.roll(x, 1)
    ) / ds**2

    ddy = (
        np.roll(y, -1) - 2.0 * y + np.roll(y, 1)
    ) / ds**2

    denominator = (dx**2 + dy**2)**1.5

    curvature = np.zeros_like(x)
    valid = denominator > 1e-12

    curvature[valid] = (
        dx[valid] * ddy[valid]
        - dy[valid] * ddx[valid]
    ) / denominator[valid]

    return curvature


# ============================================================
# 4. LOAD AND VALIDATE THE TRACK
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR / "racetrack-database" / "racelines" / "Silverstone.csv"

df = pd.read_csv(CSV_PATH)
df.columns = [col.strip().lstrip("#").strip() for col in df.columns]

x = df["x_m"].to_numpy(dtype=float)
y = df["y_m"].to_numpy(dtype=float)

if not CSV_PATH.is_file():
    raise FileNotFoundError(
        f"Track file not found: {CSV_PATH}"
    )

data = np.loadtxt(
    CSV_PATH,
    delimiter=",",
    comments="#",
    ndmin=2
)

if data.ndim != 2 or data.shape[1] < 2:
    raise ValueError("CSV must contain x and y coordinate columns.")

points = data[:, :2]

if len(points) < 3:
    raise ValueError("At least three track points are required.")

if not np.all(np.isfinite(points)):
    raise ValueError("Track coordinates contain NaN or infinity.")

# Remove consecutive duplicate points.
keep = np.ones(len(points), dtype=bool)
keep[1:] = np.any(np.diff(points, axis=0) != 0, axis=1)
points = points[keep]

# Remove a repeated final copy of the first point, if present.
if len(points) > 1 and np.allclose(
    points[-1], points[0], rtol=0.0, atol=1e-9
):
    points = points[:-1]

if len(points) < 3:
    raise ValueError("Not enough distinct points to form a loop.")

# Close the original centreline.
closed_points = np.vstack((points, points[0]))

segment_lengths = np.linalg.norm(
    np.diff(closed_points, axis=0),
    axis=1
)

if np.any(segment_lengths <= 0):
    raise ValueError("Track contains zero-length segments.")

total_length = float(np.sum(segment_lengths))

if not np.isfinite(total_length) or total_length <= 0:
    raise ValueError("Invalid track length.")


# ============================================================
# 5. RESAMPLE THE CLOSED TRACK
# ============================================================

# Use an integer number of equally spaced samples.
N = max(3, int(math.ceil(total_length / TARGET_DS)))

# The last sample is one ds before the start point.
ds = total_length / N

s_original = np.concatenate((
    [0.0],
    np.cumsum(segment_lengths)
))

s = np.arange(N, dtype=float) * ds

x_original = closed_points[:, 0]
y_original = closed_points[:, 1]

x = np.interp(s, s_original, x_original)
y = np.interp(s, s_original, y_original)


# ============================================================
# 6. CURVATURE AND CORNER SPEED LIMITS
# ============================================================

x_smooth = smooth_circular(x, COORD_SMOOTH_WINDOW)
y_smooth = smooth_circular(y, COORD_SMOOTH_WINDOW)

curvature = calculate_curvature(x_smooth, y_smooth, ds)

curvature = smooth_circular(
    curvature,
    CURVATURE_SMOOTH_WINDOW
)

v_limit = np.array([
    corner_speed(curv) for curv in curvature
])


# ============================================================
# 7. ITERATIVE CYCLIC SPEED PROFILE
# ============================================================

# Start at the corner-speed limits and only reduce speeds.
v = v_limit.copy()

converged = False

for iteration in range(MAX_ITER):
    previous = v.copy()

    # Backward pass: braking constraints.
    for i in range(N - 1, -1, -1):
        j = (i + 1) % N

        v_can = math.sqrt(
            v[j]**2 + 2.0 * braking(v[j]) * ds
        )

        v[i] = min(v[i], v_can, v_limit[i])

    # Forward pass: acceleration constraints.
    for i in range(N):
        j = (i - 1) % N

        v_can = math.sqrt(
            v[j]**2 + 2.0 * acceleration(v[j]) * ds
        )

        v[i] = min(v[i], v_can, v_limit[i])

    if np.max(np.abs(v - previous)) < TOLERANCE:
        converged = True
        break

if not converged:
    raise RuntimeError(
        f"Speed profile did not converge after {MAX_ITER} iterations."
    )


# ============================================================
# 8. VALIDATE THE FINAL SPEED PROFILE
# ============================================================

if not np.all(np.isfinite(v)):
    raise ValueError("Calculated speed contains invalid values.")

if np.any(v < 0):
    raise ValueError("Negative speed detected.")

if np.any(v > V_TOP + 1e-8):
    raise ValueError("Speed exceeds the configured top speed.")

# Check every segment, including the closing segment.
braking_violation = 0.0
acceleration_violation = 0.0

for i in range(N):
    j = (i + 1) % N

    # Available braking from i to j.
    braking_limit = (
        v[j]**2 + 2.0 * braking(v[j]) * ds
    )

    braking_violation = max(
        braking_violation,
        v[i]**2 - braking_limit
    )

    # Available acceleration from i to j.
    acceleration_limit = (
        v[i]**2 + 2.0 * acceleration(v[i]) * ds
    )

    acceleration_violation = max(
        acceleration_violation,
        v[j]**2 - acceleration_limit
    )

if max(braking_violation, acceleration_violation) > 1e-5:
    raise RuntimeError(
        "Final speed profile violates a longitudinal constraint."
    )


# ============================================================
# 9. LAP TIME
# ============================================================

# Trapezoidal / average-speed approximation for each segment.
v_next = np.roll(v, -1)
v_average = (v + v_next) / 2.0

if np.any(v_average <= 0):
    raise ValueError(
        "Zero average speed found; lap time cannot be calculated."
    )

lap_time = float(np.sum(ds / v_average))

minutes = int(lap_time // 60)
seconds = lap_time - 60 * minutes

print(f"Track length: {total_length:.2f} m")
print(f"Number of samples: {N}")
print(f"Spatial step: {ds:.4f} m")
print(f"Lap time: {minutes}:{seconds:06.3f}")
print(f"Maximum speed: {np.max(v) * 3.6:.2f} km/h")
print(f"Minimum speed: {np.min(v) * 3.6:.2f} km/h")
print(f"Iterations: {iteration + 1}")
print(f"Converged: {converged}")


# ============================================================
# 10. PLOTS
# ============================================================

fig, ax = plt.subplots(1, 2, figsize=(14, 5.5))

# Speed profile.
ax[0].plot(
    s,
    v_limit * 3.6,
    "--",
    color="gray",
    linewidth=0.8,
    label="Corner speed limit"
)

ax[0].plot(
    s,
    v * 3.6,
    color="tab:red",
    linewidth=1.0,
    label="Calculated speed"
)

ax[0].set_xlabel("Distance along track (m)")
ax[0].set_ylabel("Speed (km/h)")
ax[0].set_title(f"Silverstone speed profile ({lap_time:.2f} s)")
ax[0].legend()
ax[0].grid(True)

# Track coloured by speed.
sc = ax[1].scatter(
    x,
    y,
    c=v * 3.6,
    s=4,
    cmap="turbo"
)

ax[1].set_aspect("equal", adjustable="box")
ax[1].set_xlabel("x (m)")
ax[1].set_ylabel("y (m)")
ax[1].set_title("Track coloured by calculated speed")

fig.colorbar(sc, ax=ax[1], label="Speed (km/h)")

plt.tight_layout()

output_path = SCRIPT_DIR / "lap_silverstone.png"
plt.savefig(output_path, dpi=150)
print(f"Plot saved to: {output_path}")

plt.show()
