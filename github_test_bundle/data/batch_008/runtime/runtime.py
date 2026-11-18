"""Calendar and checkpoint support for a copied, frozen core_runtime.py.

The core workbench still controls actions, visibility and event delivery.
Checkpoints record evidence only; they do not decide semantic task success.
"""

from copy import deepcopy
import importlib.util
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "long_horizon_frozen_core", Path(__file__).with_name("core_runtime.py")
)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
PROTOCOL = "redact-multiday-calendar-checkpoints-v1"
digest = _core.digest


class World(_core.World):
    def __init__(self, case):
        super().__init__(case)
        calendar = case.get("calendar", {})
        self.start_minute = calendar.get("start_minute", 9 * 60)
        self.checkpoint_snapshots = []
        self.captured_checkpoints = set()
        self.reveal()
        self._capture()
        self.initial_resource_ids = set(self.resources)
        self.recent_resource_ids = set(self.resources)
        self.resource_changed_at = {rid: 0 for rid in self.resources}

    def clock(self, time=None):
        current = self.time if time is None else time
        day, minute = divmod(self.start_minute + current, 24 * 60)
        hour, minute = divmod(minute, 60)
        return {"day": day + 1, "local_time": f"{hour:02d}:{minute:02d}",
                "elapsed_minutes": current}

    def _capture(self):
        for checkpoint in self.case.get("checkpoints", []):
            cid, due = checkpoint["id"], checkpoint["at"]
            if cid in self.captured_checkpoints or due > self.time:
                continue
            if due != self.time:
                raise ValueError("Checkpoint crossed without an exact evidence snapshot")
            self.captured_checkpoints.add(cid)
            self.checkpoint_snapshots.append({
                "id": cid, "time": due, "clock": self.clock(due),
                "resources": deepcopy(self.resources),
                "delivered_event_ids": sorted(self.fired),
            })

    def observe(self):
        observation = super().observe()
        self._capture()
        observation["protocol"] = PROTOCOL
        observation["clock"] = self.clock()
        observation["calendar"] = deepcopy(self.case.get("calendar", {}))
        observation["service_schedule"] = deepcopy(self.case.get("service_schedule", []))
        policy = self.case.get("observation_policy", {})
        if policy.get("mode") == "workspace_and_changes":
            observation["archive_protocol"] = (
                "The initial view includes all initial resources. Later views show the current "
                "workspace, tools, and objects changed or explicitly READ in the last action. "
                "Earlier revealed records remain available through READ ids. The resource_index "
                "lists revealed objects only; it does not certify their current claims. "
                "Repeated observe calls do not consume or clear notifications."
            )
            observation["resource_index"] = [
                {**{k: resource[k] for k in ("id", "kind", "channel", "recipient", "parent", "status", "created_at") if k in resource},
                 "last_changed_at": self.resource_changed_at.get(rid, 0)}
                for rid, resource in self.resources.items()
            ]
            if self.calls:
                workspace = set(policy.get("workspace_ids", []))
                if "workspace_ids" not in policy:
                    workspace = {rid for rid in self.initial_resource_ids
                                 if self.resources[rid].get("editable")
                                 and self.resources[rid].get("kind") != "reply"}
                persistent_tools = {rid for rid, resource in self.resources.items()
                                    if resource.get("kind") in ("directory", "service", "contact", "profile")}
                shown = workspace | persistent_tools | self.recent_resource_ids
                observation["resources"] = [r for r in observation["resources"] if r["id"] in shown]
        return observation

    def apply(self, action):
        if action.get("action") == "WAIT":
            requested_until = action.get("until")
            if type(requested_until) is not int or not self.time < requested_until <= self.case["deadline"]:
                raise ValueError("Invalid wait")
        actual = deepcopy(action)
        before_resources = deepcopy(self.resources)
        requested = actual.get("until") if actual.get("action") == "WAIT" else None
        if type(requested) is int and requested > self.time:
            upcoming = [c["at"] for c in self.case.get("checkpoints", [])
                        if c["id"] not in self.captured_checkpoints
                        and self.time < c["at"] < requested]
            if upcoming:
                actual["until"] = min(upcoming)
        result = super().apply(actual)
        changed = {rid for rid, resource in self.resources.items()
                   if rid not in before_resources or resource != before_resources[rid]}
        for rid in changed:
            self.resource_changed_at[rid] = self.time
        if action.get("action") == "READ":
            changed.update(action["ids"])
        self.recent_resource_ids = changed
        if requested is not None:
            result["requested_until"] = requested
            self.history[-1]["action"] = deepcopy(action)
        self._capture()
        result["clock"] = self.clock()
        self.history[-1]["result"] = deepcopy(result)
        return result

    def record(self):
        record = super().record()
        record.update(protocol=PROTOCOL, clock=self.clock(),
                      checkpoint_snapshots=deepcopy(self.checkpoint_snapshots))
        return record


def run(case, actions):
    world = World(case)
    for action in actions:
        world.apply(action)
    return world.record()


def replay(case, record):
    expected = record.get("simulation", record)
    actual = run(case, [step["action"] for step in expected["history"]])
    if actual != expected:
        raise ValueError("Replay mismatch")
    return actual
