# Shimeji 行为基线

本基线对应行为层迁移 Map 的 Step 0。它记录当前行为引擎已经保护的能力，以及仍按降级语义处理的 Shimeji 动作。

## 已正常工作的基础动作

- `idle`：可通过 legacy 名称解析到当前 ATRI 行为名，并能作为落地后的环境 fallback。
- `move`：支持 `TargetX` / `TargetY` 目标推进，能按 ground、ceiling、wall 边界吸附。
- `fall`：支持重力、阻力和分步落地探测，可在失去边界时作为 fallback。
- `drag`：鼠标按下时只在当前动作可拖拽时切换到 Dragged。
- `thrown`：只有真实拖拽中 release 才会切到 Thrown。
- `jump`：支持目标点跳跃和朝向调整。
- `forced action`：`force_action()` 和外部状态中的 `forced_action` 会进入 override 队列。
- `forced behavior`：`force_behavior()` 和外部状态中的 `forced_behavior` 会进入 override 队列。

## 当前已知降级动作

- `Breed`：未实现多 mascot 繁殖语义，保持普通动画/默认动作降级。
- `ThrowIE`：未实现真实窗口投掷。
- `WalkWithIE`：当前降级为 `MoveActionInstance`。
- `FallWithIE`：当前降级为 `FallActionInstance`。
- `Scan*`：未实现 affordance / mascot 扫描语义。
- `Broadcast*`：未实现多 mascot 广播语义。

## 测试保护

- `tests/test_shimeji_runtime.py` 保留 XML 解析、legacy 名称映射、系统行为、参数缓存和边界吸附测试。
- `tests/test_behavior_flow.py` 覆盖 next behavior、forced action、forced behavior 和 debug trace。
- `tests/test_drag_flow.py` 覆盖不可拖拽动作不触发 Dragged，以及未拖拽 release 不触发 Thrown。
- `tests/test_runtime_tick.py` 覆盖连续 tick 不空帧、不死循环，并保持 anchor 在明显合理范围内。
