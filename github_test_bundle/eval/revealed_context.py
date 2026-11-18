"""Lossless history encoding for candidate-visible JSON observations only."""

from copy import deepcopy


CONTEXT_VERSIONS = {
    "revealed_delta": "revealed-delta-v1",
    "revealed_history": "revealed-history-v1",
    "current_observation": "current-observation-v1",
}

DELTA_FORMAT = (
    "History contains the initial observation once, followed by chronological interactions. "
    "Each observation_delta updates the previous historical observation BEFORE that "
    "interaction's assistant response. Changes use key/index paths: set replaces or adds "
    "a value, remove deletes it, and append adds array items. Apply changes in order. "
    "record_id only identifies the containing record for readability. Assistant responses, "
    "tool results and protocol errors are retained in full. This is a lossless change log, "
    "not a summary. CURRENT OBSERVATION is the full latest visible state."
)


def observation_delta(before, after):
    """Keep changed text verbatim, including removals, order and JSON types."""
    changes = []

    def emit(op, path, record_id, **values):
        change = {"op": op, "path": path, **deepcopy(values)}
        if record_id is not None:
            change["record_id"] = record_id
        changes.append(change)

    def visit(old, new, path, record_id=None):
        if type(old) is not type(new):
            emit("set", path, record_id, value=new)
        elif isinstance(new, dict):
            record_id = new.get("id", old.get("id", record_id))
            if "id" in old and "id" in new and old["id"] != new["id"]:
                emit("set", path, record_id, value=new)
                return
            for key in old:
                if key not in new:
                    emit("remove", path + [key], record_id)
            for key, value in new.items():
                if key not in old:
                    emit("set", path + [key], record_id, value=value)
                else:
                    visit(old[key], value, path + [key], record_id)
        elif isinstance(new, list):
            for index in range(min(len(old), len(new))):
                visit(old[index], new[index], path + [index], record_id)
            for index in range(len(old) - 1, len(new) - 1, -1):
                emit("remove", path + [index], record_id)
            if len(new) > len(old):
                emit("append", path, record_id, values=new[len(old):])
        elif old != new:
            emit("set", path, record_id, value=new)

    visit(before, after, [])
    return changes


def apply_observation_delta(before, changes):
    """Reconstruct observations for offline fidelity and recovery checks."""
    value = deepcopy(before)
    for change in changes:
        path = change["path"]
        if not path:
            if change["op"] == "set":
                value = deepcopy(change["value"])
            elif change["op"] == "append":
                value.extend(deepcopy(change["values"]))
            else:
                raise ValueError("Cannot remove the observation root")
            continue
        parent = value
        for key in path[:-1]:
            parent = parent[key]
        key = path[-1]
        if change["op"] == "set":
            parent[key] = deepcopy(change["value"])
        elif change["op"] == "remove":
            del parent[key]
        elif change["op"] == "append":
            parent[key].extend(deepcopy(change["values"]))
        else:
            raise ValueError("Unknown observation delta operation")
    return value


def encode_history(interactions):
    """Never read controller snapshots, hidden state or expected answers."""
    if not interactions:
        return {"interactions": []}
    initial = interactions[0]["observation"]
    previous = initial
    events = []
    for index, row in enumerate(interactions):
        event = {"turn": index + 1}
        if index:
            event["observation_delta"] = observation_delta(previous, row["observation"])
        for field in ("assistant", "result", "protocol_error"):
            if field in row:
                event[field] = deepcopy(row[field])
        events.append(event)
        previous = row["observation"]
    return {"initial_observation": deepcopy(initial), "interactions": events}
