ACTION_WALL_CLIMB = "\u58c1\u3092\u767b\u308b"


def apply_action_target_rules(action, target_x, target_y, runtime):
    if not isinstance(action, str) and action.name == ACTION_WALL_CLIMB:
        return target_x, runtime.wall_climb_target_y()
    return target_x, target_y
