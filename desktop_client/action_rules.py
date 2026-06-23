ACTION_WALL_CLIMB = "\u58c1\u3092\u767b\u308b"


def apply_action_target_rules(action, target_x, target_y, runtime):
    if not isinstance(action, str) and action.name == ACTION_WALL_CLIMB:
        if target_y is not None and _target_y_in_work_area(target_y, runtime):
            return target_x, target_y
        return target_x, runtime.wall_climb_target_y()
    return target_x, target_y


def _target_y_in_work_area(target_y, runtime):
    work_area = runtime._work_area()
    return work_area.top <= target_y <= work_area.bottom
