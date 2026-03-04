from shapely.geometry import Point, Polygon

def is_point_in_polygons(lat, lon, polygons_config):
    """
    polygons_config should be a list of lists of coordinates:
    [
        [ [lat1, lon1], [lat2, lon2], ... ],
        [ [lat3, lon3], [lat4, lon4], ... ]
    ]
    returns True if the point is within any of the polygons.
    """
    if not polygons_config:
        return True # If no polygons defined, we assume global scope

    point = Point(float(lon), float(lat)) # Note Shapely uses (x, y) -> (lon, lat)

    for poly_coords in polygons_config:
        if len(poly_coords) < 3:
            continue
        
        # Convert [[lat, lon], ...] to [(lon, lat), ...]
        pts = [(float(coord[1]), float(coord[0])) for coord in poly_coords]
        poly = Polygon(pts)
        if poly.contains(point):
            return True

    return False
