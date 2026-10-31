def get_nested(d, keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur
def merge_dicts(a, b):
    out = dict(a)
    out.update(b)
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
    return isinstance(p, int) and 1 <= p <= 65535
