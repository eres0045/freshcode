def get_nested(d, keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur
def merge_dicts(a, b):
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge_dicts(out[k], v)
        else:
            out[k] = v
    return out
def flatten_dict(d, parent="", sep="."):
    items = {}
    for k, v in d.items():
        key = parent + sep + k if parent else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, key, sep))
        else:
            items[key] = v
    return items
def env_int(value):
    return int(value)
def validate_port(p):
    return isinstance(p, int)
