import json
import argparse
import math
import numpy as np

def draw_line(pos, line_length, w, laser_d, speed):
    line_gcode = [];
    gcode_move = "G0 X{:4.4f} Y{:4.4f} Z{:4.4f} F{:4.4f}\n"
    count_lines = math.ceil(w/laser_d);
    lines_step = (w-laser_d)/max((count_lines-1),1)
    overlap = 1-lines_step/laser_d

    line_gcode.append(gcode_move.format(pos[0]+laser_d/2, pos[1], pos[2], speed))
    y = [pos[1]+line_length, pos[1]]
    for line_num in range(count_lines):
        line_gcode.append(gcode_move.format(
            *[pos[0]+laser_d/2+line_num*lines_step, y[line_num%2], pos[2], speed]))
        line_gcode.append(gcode_move.format(
            *[pos[0]+laser_d/2+(line_num+1)*lines_step, y[line_num%2], pos[2], speed]))
    return line_gcode[:-1], overlap

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="G-code generator of laser calibration for photoresist.")
    parser.add_argument('-c', '--config_file')
    args = parser.parse_args()
    if args.config_file is None:
        raise RuntimeError("Config file not selected")
    config = json.load(open(args.config_file))

    num_series = (config["surface_mm"][1]-config["offset_mm"][1])/(config["line_mm"][1]+config["eps_mm"][1])
    values_in_series = (config["surface_mm"][0]-config["offset_mm"][0])/(config["line_mm"][0]+config["eps_mm"][0])

    tests_name = ["focus_mm",
                  "width_mm",
                  "speed_mm_s"]
    count_grid_params = [config[test] for test in tests_name]

    count_unfilled = np.sum([0 if "count" in a or "values" in a else 1
                             for a in count_grid_params])
    count_reserved = np.prod([a.get("count", len(a.get("values", [1])))
                              for a in count_grid_params])

    count_grid_values = num_series*values_in_series

    count_values = math.floor(np.power(count_grid_values/count_reserved,
                                             1/count_unfilled))
    count_grid = [a.get("count",len(a.get("values", range(count_values))))
                  for a in count_grid_params]

    print("Num testing values per dimension:\n", count_grid)

    grid_values = [a["values"] if "values" in a else
                   [a.get("values",a["start"]+i*(a["finish"]-a["start"])/(b-1))
                    for i in range(b)]
                   for a, b in zip(count_grid_params, count_grid)]
    for axle, name in zip(grid_values, tests_name):
        print(name, " values:\n",["{:.2f}".format(v) for v in axle])

    grid = [[x, y, z*60]
        for x in grid_values[0]
        for y in grid_values[1]
        for z in grid_values[2]]


    lines = [draw_line([config["offset_mm"][0]/2+(i%values_in_series)*
                (config["eps_mm"][0]+config["line_mm"][0]),
                config["offset_mm"][1]/2+math.floor(i/values_in_series)*
                (config["eps_mm"][1]+config["line_mm"][1]),
                values[0]],
               config["line_mm"][1],
               config["line_mm"][0],
               values[1],
               values[2]) for values, i in zip(grid, range(len(grid)))]


    result_file = open(config["output_path"], "w")
    #settings
    pre_steps = "G28\nG21\nG0 X{:4.4f} Y{:4.4f} Z{:4.4f}\nM400\nG92 X0 Y0\nG90\n"
    result_file.write(pre_steps.format(*[config["left_bottom"][0], config["left_bottom"][1], count_grid_params[0]["start"]]))
    #draw lines
    disable_laser = "M107 \nG4 P{:4.4f}\n"
    enable_laser = "M106 S255.0\nG4 P{:4.4f}\n"
    wait_move_finished = "M400\n"
    for line in lines:
        result_file.write(wait_move_finished)
        result_file.write(disable_laser.format(config["pause_off_ms"]))
        #move to line start
        result_file.write(line[0][0])
        result_file.write(enable_laser.format(config["pause_on_ms"]))
        result_file.write("".join(line[0][1:]))
    result_file.write(wait_move_finished)
    result_file.write(disable_laser.format(config["pause_off_ms"]))
