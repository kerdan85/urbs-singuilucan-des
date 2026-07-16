import os
import shutil
import urbs
from datetime import date

input_files = 'Input'

result_name = 'Site 1-CO2 Medio'
result_dir = urbs.prepare_result_directory(result_name)  # name + time stamp

# copy input file to result directory
try:
    shutil.copytree(input_files, os.path.join(result_dir, 'Input'))
except NotADirectoryError:
    shutil.copyfile(input_files, os.path.join(result_dir, input_files))
# copy runme.py to result directory
shutil.copy(__file__, result_dir)

# objective function
objective = 'cost' # set either 'cost' or 'CO2' as objective

# Choose Solver (cplex, glpk, gurobi, ...)
solver = 'cbc'

# simulation timesteps
# Semana demanda maxima (3265, 120)
(offset, length) = (2329, 120)  # time step selection
timesteps = range(offset, offset+length+1)
dt = 1  # length of each time step (unit: hours)

# detailed reporting commodity/sites
report_tuples = [
    (2025, 'Site1', 'Electricity'),
    (2025, 'Site1', 'Heat'),
    (2030, 'Site1', 'Electricity'),
    (2030, 'Site1', 'Heat'),
    (2035, 'Site1', 'Electricity'),
    (2035, 'Site1', 'Heat'),
    (2040, 'Site1', 'Electricity'),
    (2040, 'Site1', 'Heat')
    ]

# optional: define names for sites in report_tuples
report_sites_name = {('Site1'): 'Site1'}

# plotting commodities/sites
plot_tuples = [
    (2025, 'Site1', 'Electricity'),
    (2025, 'Site1', 'Heat'),
    (2030, 'Site1', 'Electricity'),
    (2030, 'Site1', 'Heat'),
    (2035, 'Site1', 'Electricity'),
    (2035, 'Site1', 'Heat'),
    (2040, 'Site1', 'Electricity'),
    (2040, 'Site1', 'Heat')
    ]
# optional: define names for sites in plot_tuples
plot_sites_name = {('Site1'): 'Site1'}

# plotting timesteps
plot_periods = {
    'all': timesteps[1:]
}

# add or change plot colors
my_colors = {
    'Demand': (0, 0, 0),
    'Boiler GN': (180, 50, 15),
    'Boiler GLP': (227, 114, 34),
    'Boiler Elec': (0, 101, 189),
    'Solarthermal': (255, 220, 0),
    'Heatpump': (110, 33, 20),
    'Electrolyzer': (21, 221, 222),
    'Hydrogen FC': (21, 241, 116),
    'Photovoltaics': (240, 241, 0),
    'Diesel powerplant': (80, 80, 80),
    'Purchase': (87, 30, 126),
    'Feed-in': (108, 128, 91),
    'Slack powerplant': (44, 43, 47),
    'Storage': (100, 160, 200)}
for country, color in my_colors.items():
    urbs.COLORS[country] = color

# select scenarios to be run
scenarios = [
            urbs.scenario_base,
            #urbs.scenario_stock_prices,
            #urbs.scenario_co2_limit,
            #urbs.scenario_co2_tax_mid,
            #urbs.scenario_no_dsm,
            #urbs.scenario_north_process_caps,
            #urbs.scenario_all_together
            ]

for scenario in scenarios:
    prob = urbs.run_scenario(input_files, solver, timesteps, scenario,
                        result_dir, dt, objective,
                        plot_tuples=plot_tuples,
                        plot_sites_name=plot_sites_name,
                        plot_periods=plot_periods,
                        report_tuples=report_tuples,
                        report_sites_name=report_sites_name)
