import dxfgrabber
try:
    dxf = dxfgrabber.readfile('c:\\Users\\TIH06\\Downloads\\GPR\\requirements\\static\\ALLGRIDS.dxf')
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    count = 0
    for entity in dxf.entities:
        pts = []
        if entity.dxftype == 'LINE':
            pts = [entity.start, entity.end]
        elif entity.dxftype in ['LWPOLYLINE', 'POLYLINE']:
            pts = entity.points
        
        for p in pts:
            x, y = p[0], p[1]
            if x < min_x: min_x = x
            if x > max_x: max_x = x
            if y < min_y: min_y = y
            if y > max_y: max_y = y
            count += 1
    
    print(f'Count: {count}')
    print(f'Bounds: X[{min_x}, {max_x}] Y[{min_y}, {max_y}]')
except Exception as e:
    print(f'Error: {e}')
