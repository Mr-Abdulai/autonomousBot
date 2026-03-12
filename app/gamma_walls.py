class GammaWallDetector:
    """
    Institutional Upgrade 4: Synthetic Options Gamma Walls.
    Detects proximity to massive institutional round-number options strikes (e.g. 2300, 2400)
    which act as heavy magnets and severe rejection zones.
    """
    def __init__(self, danger_zone_dollars=5.0):
        # For Gold, $100 intervals (2200, 2300) are massive Options Expiries. 
        # $50 (2250, 2350) are secondary but still potent.
        # Danger zone: Within $5.00 of the wall.
        self.danger_zone = danger_zone_dollars 

    def analyze(self, current_price: float) -> dict:
        """
        Calculates distance to nearest upper and lower Gamma Walls.
        Returns defensive risk constraints.
        """
        closest_wall = 0
        distance = 99999
        wall_type = "NONE"
        
        # 1. Find nearest Major Wall ($100)
        major_lower = (int(current_price) // 100) * 100
        major_upper = major_lower + 100
        
        d_lower = current_price - major_lower
        d_upper = major_upper - current_price
        
        if d_lower < d_upper:
            closest_wall = major_lower
            distance = d_lower
            wall_type = "MAJOR"
        else:
            closest_wall = major_upper
            distance = d_upper
            wall_type = "MAJOR"
            
        # 2. Check minor walls ($50 thresholds) if major is far
        if distance > self.danger_zone:
            minor_lower = (int(current_price) // 50) * 50
            minor_upper = minor_lower + 50
            
            dm_lower = current_price - minor_lower
            dm_upper = minor_upper - current_price
            
            min_minor_dist = min(dm_lower, dm_upper)
            if min_minor_dist < distance and min_minor_dist <= self.danger_zone:
                closest_wall = minor_lower if dm_lower < dm_upper else minor_upper
                distance = min_minor_dist
                wall_type = "MINOR"

        # Construct Defense Profile
        is_danger = distance <= self.danger_zone
        
        # If wall is above us, we are pushing up into it.
        wall_direction = "ABOVE" if closest_wall > current_price else "BELOW"
        
        return {
            'near_wall': is_danger,
            'wall_price': closest_wall,
            'distance': distance,
            'wall_type': wall_type,
            'direction': wall_direction,
            'ts_multiplier': 0.4 if is_danger else 1.0, # Squeeze Trailing Stops by 60% near walls
            'block_buy': is_danger and wall_direction == "ABOVE" and distance < 2.5,  # Block BUYS right under a ceiling
            'block_sell': is_danger and wall_direction == "BELOW" and distance < 2.5  # Block SELLS right above a floor
        }
