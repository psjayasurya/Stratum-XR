with open('c:\\Users\\TIH06\\Downloads\\GPR\\requirements\\static\\ALLGRIDS.dxf', 'r') as f:
    lines = f.read().splitlines()

min_x = min_y = float('inf')
max_x = max_y = float('-inf')

current_code = None
for line in lines:
    line = line.strip()
    try:
        val = float(line)
        if current_code == '10':
            if val < min_x: min_x = val
            if val > max_x: max_x = val
        elif current_code == '20':
            if val < min_y: min_y = val
            if val > max_y: max_y = val
        current_code = line
    except ValueError:
        current_code = line

print(f'Bounds: X[{min_x}, {max_x}] Y[{min_y}, {max_y}]')
