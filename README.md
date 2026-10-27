# Silverstone Lap Time Simulator

# silverstone-lap-simulator

A Python-based simulation of Formula 1 lap performance at the Silverstone Circuit, using track geometry to estimate a speed profile and calculate lap time.

## Description

This project simulates a Formula 1 car completing a lap of the Silverstone Circuit. Instead of assuming a constant speed throughout the lap, the model uses track geometry to estimate how the car's speed changes along the circuit.

The simulation loads raceline data from a CSV file and calculates the curvature of the track at different points. This curvature is then used to estimate the maximum speed the car can maintain through each section of the circuit, accounting for the relationship between cornering speed and track curvature.

A cyclic speed profile is generated to represent a complete lap, taking into account the sequence of corners and straights around the circuit. The resulting speed profile is used to estimate the total lap time.

The project also generates a visualization of the simulated lap, making it easier to examine how track geometry influences the car's speed throughout the circuit.

**Note:** This is a simplified simulation model intended for educational and exploratory purposes. The calculated speed profile and lap time depend on the input raceline data and the assumptions implemented in the model. They should not be interpreted as official Formula 1 telemetry or an exact prediction of real-world lap performance.

## Technologies Used

- **Python** — core simulation and calculations
- **NumPy** — numerical operations and track geometry calculations
- **Pandas** — loading and processing raceline data from CSV files
- **Matplotlib** — visualizing simulation results

## Requirements

- Python 3
- NumPy
- Pandas
- Matplotlib
- Silverstone raceline data in CSV format

## Usage

1. Clone or download this repository.
2. Make sure the required Python libraries are installed.
3. Ensure that the Silverstone raceline CSV file is available at `racetrack-database/racelines/Silverstone.csv`.
4. Open `main.py` in Python or PyCharm and run the script.
5. The simulation processes the track geometry, generates a speed profile, and calculates the estimated lap time.
6. A plot of the simulation results is saved as `lap_silverstone.png` in the script's directory.

## Simulation Results

The simulation generates a visualization of the car's speed profile around the Silverstone Circuit.

![Silverstone Lap Simulation](lap_silverstone.png)

## Project Structure

- `main.py` — main simulation script
- `racetrack-database/racelines/Silverstone.csv` — input raceline data
- `lap_silverstone.png` — generated visualization of the simulation results

## Future Improvements

Potential extensions include incorporating vehicle acceleration and braking limits, tire grip, aerodynamic downforce, and more detailed vehicle dynamics to produce a more realistic lap-time simulation.
